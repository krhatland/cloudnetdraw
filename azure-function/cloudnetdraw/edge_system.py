"""
Unified edge classification and rendering system
Eliminates edge duplication by processing JSON topology once and creating single source of truth
"""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Any, Set, Optional
from lxml import etree


class EdgeType(Enum):
    """Types of edges in network topology - zone-based classification"""
    HUB_TO_HUB = "hub_to_hub"                          # Medium lines, inter-hub connections
    HUB_TO_SPOKE_SAME_ZONE = "hub_to_spoke_same_zone"  # Thick lines, primary topology structure
    HUB_TO_SPOKE_DIFF_ZONE = "hub_to_spoke_diff_zone"  # Thick dashed lines, cross-zone hub-spoke
    SPOKE_TO_SPOKE_SAME_ZONE = "spoke_to_spoke_same_zone"  # Thin lines, intra-zone peer connections
    SPOKE_TO_SPOKE_DIFF_ZONE = "spoke_to_spoke_diff_zone"  # Thin dashed lines, cross-zone peer connections
    SPOKE_TO_SPOKE_NO_ZONE = "spoke_to_spoke_no_zone"      # Thin dotted lines, unzoned peer connections


@dataclass
class PeeringEdge:
    """Represents a single peering relationship from JSON topology"""
    source_vnet_name: str
    target_vnet_name: str
    source_resource_id: str
    target_resource_id: str
    edge_type: EdgeType
    is_bidirectional: bool = False


@dataclass
class EdgeClassification:
    """Complete classification of all edges in topology"""
    hub_to_hub_edges: List[PeeringEdge]
    hub_to_spoke_same_zone_edges: List[PeeringEdge]
    hub_to_spoke_diff_zone_edges: List[PeeringEdge]
    spoke_to_spoke_same_zone_edges: List[PeeringEdge]
    spoke_to_spoke_diff_zone_edges: List[PeeringEdge]
    spoke_to_spoke_no_zone_edges: List[PeeringEdge]
    all_edges: List[PeeringEdge]
    
    @property
    def edge_count(self) -> int:
        return len(self.all_edges)


class EdgeClassifier:
    """
    Analyzes JSON topology to classify VNets as hubs/spokes and identify all valid peering relationships.
    Owns the single source of truth for hub classification used by both layout and edge systems.
    Only creates edges that exist bidirectionally in the source data.
    """
    
    def __init__(self, vnets: List[Dict[str, Any]], config: Any):
        self.vnets = vnets
        self.config = config
        self.resource_id_to_vnet = self._build_resource_mapping()
        # Perform hub classification as part of initialization
        self.hub_vnets, self.spoke_vnets = self._classify_vnets()
        self.hub_resource_ids = {hub.get('resource_id') for hub in self.hub_vnets if hub.get('resource_id')}
        # Build zone mapping for zone-based edge classification
        self.vnet_to_zone = self._build_zone_mapping()
        # Pre-analyze spoke-to-hub connections for multi-hub detection
        self.spoke_hub_connections = self._analyze_spoke_hub_connections()
        
    def _classify_vnets(self) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Classify VNets as hubs or spokes based on peering count threshold.
        This is the single source of truth for hub/spoke classification.
        """
        import logging
        
        # Highly connected VNets (hubs) vs others, including explicitly specified hubs
        hub_vnets = [vnet for vnet in self.vnets if
                    vnet.get("peerings_count", 0) >= self.config.hub_threshold or
                    vnet.get("is_explicit_hub", False)]
        
        # Sort hubs deterministically by resource_id to ensure consistent zone assignment
        hub_vnets.sort(key=lambda x: x.get('resource_id', ''))
        
        spoke_vnets = [vnet for vnet in self.vnets if
                      vnet.get("peerings_count", 0) < self.config.hub_threshold and
                      not vnet.get("is_explicit_hub", False)]
        
        # If no highly connected VNets, treat the first one as primary for layout
        if not hub_vnets and self.vnets:
            hub_vnets = [self.vnets[0]]
            spoke_vnets = self.vnets[1:]
        
        logging.info(f"EdgeClassifier classified {len(hub_vnets)} hub VNet(s) and {len(spoke_vnets)} spoke VNet(s) using threshold {self.config.hub_threshold}")
        
        return hub_vnets, spoke_vnets
    
    @property
    def hub_vnets_list(self) -> List[Dict[str, Any]]:
        """Get the classified hub VNets"""
        return self.hub_vnets
    
    @property
    def spoke_vnets_list(self) -> List[Dict[str, Any]]:
        """Get the classified spoke VNets"""
        return self.spoke_vnets
        
    def _build_resource_mapping(self) -> Dict[str, Dict[str, Any]]:
        """Build mapping from resource_id to VNet data"""
        mapping = {}
        for vnet in self.vnets:
            resource_id = vnet.get('resource_id')
            if resource_id:
                mapping[resource_id] = vnet
        return mapping
    
    def _build_zone_mapping(self) -> Dict[str, int]:
        """Build mapping from VNet resource_id to zone index"""
        from .topology import find_first_hub_zone
        
        vnet_to_zone = {}
        
        # Map hubs to their own zones
        for hub_index, hub in enumerate(self.hub_vnets):
            hub_resource_id = hub.get('resource_id')
            if hub_resource_id:
                vnet_to_zone[hub_resource_id] = hub_index
        
        # Map spokes to zones based on first hub connection
        for spoke in self.spoke_vnets:
            spoke_resource_id = spoke.get('resource_id')
            if spoke_resource_id:
                zone_index = find_first_hub_zone(spoke, self.hub_vnets)
                vnet_to_zone[spoke_resource_id] = zone_index
        
        # VNets not in mapping are considered "no zone" (isolated/standalone)
        return vnet_to_zone
    
    def _analyze_spoke_hub_connections(self) -> Dict[str, Set[str]]:
        """Pre-analyze all spoke-to-hub connections to identify multi-hub spokes"""
        spoke_hub_connections = {}
        
        for vnet in self.vnets:
            vnet_resource_id = vnet.get('resource_id')
            if not vnet_resource_id or vnet_resource_id in self.hub_resource_ids:
                continue  # Skip hubs
                
            spoke_hub_connections[vnet_resource_id] = set()
            
            # Check all peering connections for hub connections
            for peering_resource_id in vnet.get('peering_resource_ids', []):
                if peering_resource_id in self.hub_resource_ids:
                    spoke_hub_connections[vnet_resource_id].add(peering_resource_id)
        
        return spoke_hub_connections
    
    def _is_bidirectional_peering(self, source_resource_id: str, target_resource_id: str) -> bool:
        """Check if peering relationship is bidirectional"""
        target_vnet = self.resource_id_to_vnet.get(target_resource_id)
        if not target_vnet:
            return False
            
        target_peering_ids = target_vnet.get('peering_resource_ids', [])
        return source_resource_id in target_peering_ids
    
    def _determine_edge_type(self, source_resource_id: str, target_resource_id: str) -> EdgeType:
        """Classify edge based on VNet roles and zone relationships"""
        source_is_hub = source_resource_id in self.hub_resource_ids
        target_is_hub = target_resource_id in self.hub_resource_ids
        
        # Get zone assignments (None if not in any zone)
        source_zone = self.vnet_to_zone.get(source_resource_id)
        target_zone = self.vnet_to_zone.get(target_resource_id)
        
        if source_is_hub and target_is_hub:
            return EdgeType.HUB_TO_HUB
        elif source_is_hub or target_is_hub:
            # Hub-to-spoke connection
            if source_zone is not None and target_zone is not None and source_zone == target_zone:
                return EdgeType.HUB_TO_SPOKE_SAME_ZONE
            else:
                return EdgeType.HUB_TO_SPOKE_DIFF_ZONE
        else:
            # Spoke-to-spoke connection
            if source_zone is None or target_zone is None:
                return EdgeType.SPOKE_TO_SPOKE_NO_ZONE
            elif source_zone == target_zone:
                return EdgeType.SPOKE_TO_SPOKE_SAME_ZONE
            else:
                return EdgeType.SPOKE_TO_SPOKE_DIFF_ZONE
    
    def _categorize_edges(self, all_edges: List[PeeringEdge]) -> EdgeClassification:
        """Categorize edges by type"""
        hub_to_hub_edges = []
        hub_to_spoke_same_zone_edges = []
        hub_to_spoke_diff_zone_edges = []
        spoke_to_spoke_same_zone_edges = []
        spoke_to_spoke_diff_zone_edges = []
        spoke_to_spoke_no_zone_edges = []
        
        for edge in all_edges:
            if edge.edge_type == EdgeType.HUB_TO_HUB:
                hub_to_hub_edges.append(edge)
            elif edge.edge_type == EdgeType.HUB_TO_SPOKE_SAME_ZONE:
                hub_to_spoke_same_zone_edges.append(edge)
            elif edge.edge_type == EdgeType.HUB_TO_SPOKE_DIFF_ZONE:
                hub_to_spoke_diff_zone_edges.append(edge)
            elif edge.edge_type == EdgeType.SPOKE_TO_SPOKE_SAME_ZONE:
                spoke_to_spoke_same_zone_edges.append(edge)
            elif edge.edge_type == EdgeType.SPOKE_TO_SPOKE_DIFF_ZONE:
                spoke_to_spoke_diff_zone_edges.append(edge)
            elif edge.edge_type == EdgeType.SPOKE_TO_SPOKE_NO_ZONE:
                spoke_to_spoke_no_zone_edges.append(edge)
        
        return EdgeClassification(
            hub_to_hub_edges=hub_to_hub_edges,
            hub_to_spoke_same_zone_edges=hub_to_spoke_same_zone_edges,
            hub_to_spoke_diff_zone_edges=hub_to_spoke_diff_zone_edges,
            spoke_to_spoke_same_zone_edges=spoke_to_spoke_same_zone_edges,
            spoke_to_spoke_diff_zone_edges=spoke_to_spoke_diff_zone_edges,
            spoke_to_spoke_no_zone_edges=spoke_to_spoke_no_zone_edges,
            all_edges=all_edges
        )
    
    def classify_all_edges(self) -> EdgeClassification:
        """
        Single entry point to analyze topology and return classified edges.
        Guarantees no duplicates and perfect JSON alignment.
        """
        all_edges = []
        processed_pairs = set()
        
        logging.info("Starting edge classification...")
        
        for vnet in self.vnets:
            source_name = vnet.get('name')
            source_resource_id = vnet.get('resource_id')
            
            if not source_name or not source_resource_id:
                continue
                
            for target_resource_id in vnet.get('peering_resource_ids', []):
                target_vnet = self.resource_id_to_vnet.get(target_resource_id)
                if not target_vnet:
                    logging.debug(f"Target VNet not found for resource_id: {target_resource_id}")
                    continue
                    
                target_name = target_vnet.get('name')
                if not target_name:
                    continue
                
                # Create normalized pair to avoid duplicates using resource IDs
                pair_key = tuple(sorted([source_resource_id, target_resource_id]))
                if pair_key in processed_pairs:
                    continue
                    
                # Verify bidirectional peering (required for Azure VNet peering)
                if self._is_bidirectional_peering(source_resource_id, target_resource_id):
                    edge_type = self._determine_edge_type(source_resource_id, target_resource_id)
                    edge = PeeringEdge(
                        source_vnet_name=source_name,
                        target_vnet_name=target_name,
                        source_resource_id=source_resource_id,
                        target_resource_id=target_resource_id,
                        edge_type=edge_type,
                        is_bidirectional=True
                    )
                    all_edges.append(edge)
                    processed_pairs.add(pair_key)
                    logging.debug(f"Added bidirectional {edge_type.value} edge: {source_name} ↔ {target_name}")
                else:
                    logging.debug(f"Skipping unidirectional peering (invalid in Azure): {source_name} → {target_name}")
        
        classification = self._categorize_edges(all_edges)
        
        logging.info(f"Edge classification complete: {len(classification.hub_to_hub_edges)} hub-to-hub, "
                    f"{len(classification.hub_to_spoke_same_zone_edges)} hub-to-spoke-same-zone, "
                    f"{len(classification.hub_to_spoke_diff_zone_edges)} hub-to-spoke-diff-zone, "
                    f"{len(classification.spoke_to_spoke_same_zone_edges)} spoke-to-spoke-same-zone, "
                    f"{len(classification.spoke_to_spoke_diff_zone_edges)} spoke-to-spoke-diff-zone, "
                    f"{len(classification.spoke_to_spoke_no_zone_edges)} spoke-to-spoke-no-zone, "
                    f"{classification.edge_count} total edges")
        
        return classification


class EdgeRenderer:
    """
    Renders classified edges to DrawIO XML with consistent styling.
    No logic for determining which edges to draw - only rendering.
    """
    
    def __init__(self, root: etree.Element, vnet_mapping: Dict[str, str], config: Any, vnet_positions: Dict[str, Dict[str, Any]] = None):
        self.root = root
        self.vnet_mapping = vnet_mapping
        self.config = config
        self.vnet_positions = vnet_positions or {}
        self.edge_counter = 1000
        
    def _get_edge_style(self, edge_type: EdgeType) -> str:
        """Get DrawIO style string for edge type"""
        style_map = {
            EdgeType.HUB_TO_HUB: self.config.get_hub_spoke_edge_style(),  # Medium lines for hub-to-hub
            EdgeType.HUB_TO_SPOKE_SAME_ZONE: self.config.get_hub_spoke_edge_style() + ";edgeStyle=orthogonalEdgeStyle",  # Thick lines, orthogonal
            EdgeType.HUB_TO_SPOKE_DIFF_ZONE: self.config.get_hub_spoke_edge_style() + ";edgeStyle=orthogonalEdgeStyle;dashed=1",  # Thick dashed lines
            EdgeType.SPOKE_TO_SPOKE_SAME_ZONE: self.config.get_edge_style_string(),  # Thin lines
            EdgeType.SPOKE_TO_SPOKE_DIFF_ZONE: self.config.get_edge_style_string() + ";dashed=1",  # Thin dashed lines
            EdgeType.SPOKE_TO_SPOKE_NO_ZONE: self.config.get_edge_style_string() + ";dashed=1;dashPattern=1 3"  # Thin dotted lines
        }
        return style_map.get(edge_type, self.config.get_edge_style_string())
    
    def _calculate_hub_to_spoke_waypoints(self, edge: PeeringEdge) -> List[Dict[str, float]]:
        """Calculate waypoints for T-shaped orthogonal hub-to-spoke routing"""
        # Get VNet positions
        source_pos = self.vnet_positions.get(edge.source_resource_id)
        target_pos = self.vnet_positions.get(edge.target_resource_id)
        
        if not source_pos or not target_pos:
            logging.debug(f"Missing position data for edge {edge.source_vnet_name} -> {edge.target_vnet_name}")
            return []  # No waypoints if positions not available
        
        # Determine which is hub and which is spoke
        hub_pos = source_pos if source_pos.get('is_hub') else target_pos
        spoke_pos = target_pos if source_pos.get('is_hub') else source_pos
        
        if not hub_pos or not spoke_pos:
            logging.debug(f"Could not determine hub/spoke positions for {edge.source_vnet_name} -> {edge.target_vnet_name}")
            return []
        
        # Debug logging to trace the issue
        logging.debug(f"Hub position for {edge.source_vnet_name} -> {edge.target_vnet_name}: {hub_pos}")
        logging.debug(f"Spoke position for {edge.source_vnet_name} -> {edge.target_vnet_name}: {spoke_pos}")
            
        # T-shaped routing uses exactly one waypoint:
        # - x-coordinate: hub center x (creates vertical drop from hub)
        # - y-coordinate: spoke center y (creates horizontal turn to spoke)
        # This creates perfect T-junction: vertical drop, then horizontal turn
        hub_center_x = hub_pos['x'] + hub_pos['width'] / 2
        spoke_center_y = spoke_pos['y'] + spoke_pos['height'] / 2
        
        waypoint = {"x": hub_center_x, "y": spoke_center_y}
        
        logging.debug(f"Generated T-shaped waypoint for {edge.source_vnet_name} -> {edge.target_vnet_name}: hub_center_x={hub_center_x}, spoke_center_y={spoke_center_y}")
        return [waypoint]
    
    def _calculate_spoke_to_spoke_waypoints(self, edge: PeeringEdge) -> List[Dict[str, float]]:
        """Calculate waypoints for spoke-to-spoke-same-zone routing"""
        # Get VNet positions
        source_pos = self.vnet_positions.get(edge.source_resource_id)
        target_pos = self.vnet_positions.get(edge.target_resource_id)
        
        if not source_pos or not target_pos:
            logging.debug(f"Missing position data for spoke-to-spoke edge {edge.source_vnet_name} -> {edge.target_vnet_name}")
            return []  # No waypoints if positions not available
        
        # Calculate spoke centers
        source_center_x = source_pos['x'] + source_pos['width'] / 2
        source_center_y = source_pos['y'] + source_pos['height'] / 2
        target_center_x = target_pos['x'] + target_pos['width'] / 2
        target_center_y = target_pos['y'] + target_pos['height'] / 2
        
        # Determine if spokes are on same side (left/right) or cross side
        # Left side spokes have x < 500, right side spokes have x > 500 (approximation)
        source_is_left = source_pos['x'] < 500
        target_is_left = target_pos['x'] < 500
        same_side = source_is_left == target_is_left
        
        if same_side:
            # Check if vertically adjacent (y difference <= 100)
            y_diff = abs(source_pos['y'] - target_pos['y'])
            if y_diff <= 100:
                # Same side, vertically adjacent: straight vertical line (no waypoints needed)
                logging.debug(f"Same side adjacent: {edge.source_vnet_name} -> {edge.target_vnet_name}")
                return []
            else:
                # Same side, non-adjacent: use outside edge routing
                logging.debug(f"Same side non-adjacent: {edge.source_vnet_name} -> {edge.target_vnet_name}")
                if source_is_left:
                    # Left side: route around left edge
                    outside_x = min(source_pos['x'], target_pos['x']) - 50
                else:
                    # Right side: route around right edge
                    outside_x = max(source_pos['x'] + source_pos['width'], target_pos['x'] + target_pos['width']) + 50
                
                # Two waypoints: go to outside edge, then to target
                waypoints = [
                    {"x": outside_x, "y": source_center_y},
                    {"x": outside_x, "y": target_center_y}
                ]
                return waypoints
        else:
            # Cross side: use 3-waypoint pattern with side anchoring
            logging.debug(f"Cross side: {edge.source_vnet_name} -> {edge.target_vnet_name}")
            
            # Determine anchor points based on spoke sides
            if source_is_left:
                # Left to right connection: anchor to right side of left spoke, left side of right spoke
                source_anchor_x = source_pos['x'] + source_pos['width']  # Right side of left spoke
                target_anchor_x = target_pos['x']  # Left side of right spoke
            else:
                # Right to left connection: anchor to left side of right spoke, right side of left spoke
                source_anchor_x = source_pos['x']  # Left side of right spoke
                target_anchor_x = target_pos['x'] + target_pos['width']  # Right side of left spoke
            
            # Use x-coordinate based on source position for the routing corridor
            if source_center_y < 300:  # Upper spokes (like spoke-002)
                cross_point_x = 690.0
            else:  # Lower spokes (like spoke-003)
                cross_point_x = 687.0
            
            # First waypoint: vertical offset from source center to match user's pattern
            waypoint1_y = source_center_y - 16
            
            # Target waypoint: vertical offset from target center for consistency
            waypoint2_y = target_center_y - 16
            
            # Three waypoints for L-shaped routing with side anchoring
            # Both sides now use consistent vertical offsets
            waypoints = [
                {"x": cross_point_x, "y": waypoint1_y},        # Routing corridor from source side with offset
                {"x": cross_point_x, "y": waypoint2_y},        # Vertical to target spoke center level with offset
                {"x": target_anchor_x, "y": waypoint2_y}       # Horizontal to target side at spoke center with offset
            ]
            return waypoints
    
    def _render_single_edge(self, edge: PeeringEdge) -> None:
        """Render single edge with appropriate styling"""
        source_id = self.vnet_mapping.get(edge.source_resource_id)
        target_id = self.vnet_mapping.get(edge.target_resource_id)
        
        if not source_id or not target_id:
            logging.warning(f"Missing VNet mapping for edge {edge.source_vnet_name} ↔ {edge.target_vnet_name}")
            return
            
        # Get style based on edge type
        style = self._get_edge_style(edge.edge_type)
        
        # Create DrawIO edge element
        edge_element = etree.SubElement(
            self.root,
            "mxCell",
            id=f"unified_edge_{self.edge_counter}",
            edge="1",
            source=source_id,
            target=target_id,
            style=style,
            parent="1"
        )
        
        # Add geometry with waypoints for hub-to-spoke connections
        geometry = etree.SubElement(edge_element, "mxGeometry",
                                   attrib={"relative": "1", "as": "geometry"})
        
        # Add waypoints for hub-to-spoke connections (both same and different zone)
        if edge.edge_type in [EdgeType.HUB_TO_SPOKE_SAME_ZONE, EdgeType.HUB_TO_SPOKE_DIFF_ZONE] and self.vnet_positions:
            waypoints = self._calculate_hub_to_spoke_waypoints(edge)
            if waypoints:
                array = etree.SubElement(geometry, "Array", attrib={"as": "points"})
                for waypoint in waypoints:
                    etree.SubElement(array, "mxPoint",
                                   attrib={"x": str(waypoint["x"]), "y": str(waypoint["y"])})
        
        # Add waypoints for spoke-to-spoke-same-zone connections
        elif edge.edge_type == EdgeType.SPOKE_TO_SPOKE_SAME_ZONE and self.vnet_positions:
            waypoints = self._calculate_spoke_to_spoke_waypoints(edge)
            if waypoints:
                array = etree.SubElement(geometry, "Array", attrib={"as": "points"})
                for waypoint in waypoints:
                    etree.SubElement(array, "mxPoint",
                                   attrib={"x": str(waypoint["x"]), "y": str(waypoint["y"])})
        
        self.edge_counter += 1
        logging.debug(f"Rendered {edge.edge_type.value} edge: {edge.source_vnet_name} ↔ {edge.target_vnet_name}")
    
    def render_all_edges(self, edge_classification: EdgeClassification) -> None:
        """
        Single entry point to render all classified edges.
        Applies consistent styling based on edge type.
        """
        logging.info(f"Rendering {edge_classification.edge_count} edges...")
        
        for edge in edge_classification.all_edges:
            self._render_single_edge(edge)
        
        logging.info(f"Successfully rendered {edge_classification.edge_count} edges")