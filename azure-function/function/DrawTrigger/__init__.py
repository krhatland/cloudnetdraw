import os
import json
import logging
from datetime import datetime

import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

# Import CloudNetDraw library modules
import cloudnetdraw.azure_client as azure_client
from cloudnetdraw.config import Config
from cloudnetdraw.diagram_generator import generate_mld_diagram, generate_hld_diagram


def main(mytimer: func.TimerRequest) -> None:
    """Azure Function entrypoint for generating network diagrams.

    This timer-triggered function collects Azure networking topology using
    Managed Identity authentication, saves the topology as JSON, and
    generates both mid-level (MLD) and high-level (HLD) Draw.io diagrams
    using the CloudNetDraw library.  The resulting files are uploaded
    to a specified Blob Storage container.
    """
    logging.info("DrawTrigger function triggered")

    # Create a timestamp for file naming
    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")

    # Initialize credentials for CloudNetDraw using Managed Identity.
    # CloudNetDraw normally uses Azure CLI credentials by default.  For
    # self-hosted deployments (Functions with a system-assigned identity), we
    # explicitly set the internal credential to DefaultAzureCredential so that
    # all Azure SDK clients authenticate using Managed Identity.
    azure_client._credentials = DefaultAzureCredential()

    # Discover all subscriptions available to this identity
    try:
        subscription_ids = azure_client.get_all_subscription_ids()
        logging.info(f"Found {len(subscription_ids)} subscriptions: {subscription_ids}")
    except Exception as e:
        logging.error(f"Failed to list subscriptions: {e}")
        return

    # Build the full VNet topology across the subscriptions
    try:
        topology = azure_client.get_vnet_topology_for_selected_subscriptions(subscription_ids)
    except Exception as e:
        logging.error(f"Failed to retrieve VNet topology: {e}")
        return

    # Persist topology to a temporary JSON file in /tmp
    json_file_name = f"{timestamp}_network_topology.json"
    json_file_path = f"/tmp/{json_file_name}"
    try:
        with open(json_file_path, "w") as json_file:
            json.dump(topology, json_file, indent=2)
        logging.info(f"Saved topology JSON to {json_file_path}")
    except Exception as e:
        logging.error(f"Failed to write topology JSON: {e}")
        return

    # Prepare diagram file paths
    diagram_file_name_mld = f"{timestamp}_network_diagram_MLD.drawio"
    diagram_file_path_mld = f"/tmp/{diagram_file_name_mld}"
    diagram_file_name_hld = f"{timestamp}_network_diagram_HLD.drawio"
    diagram_file_path_hld = f"/tmp/{diagram_file_name_hld}"

    # Load default configuration for diagram styling and thresholds
    config = Config()

    # Generate diagrams using CloudNetDraw
    try:
        generate_mld_diagram(diagram_file_path_mld, json_file_path, config)
        logging.info(f"Generated MLD diagram at {diagram_file_path_mld}")
        generate_hld_diagram(diagram_file_path_hld, json_file_path, config)
        logging.info(f"Generated HLD diagram at {diagram_file_path_hld}")
    except Exception as e:
        logging.error(f"Failed to generate diagrams: {e}")
        return

    # Upload the JSON and diagrams to Blob Storage
    account_url = os.environ.get("DRAWING_STORAGE_URL")
    container_name = os.environ.get("DRAWING_CONTAINER_NAME")
    if not account_url or not container_name:
        logging.error("Storage configuration missing: DRAWING_STORAGE_URL and DRAWING_CONTAINER_NAME must be set")
        return

    # Use Managed Identity to authenticate with Blob Storage
    blob_service_client = BlobServiceClient(account_url=account_url, credential=DefaultAzureCredential())

    def upload_file(blob_name: str, file_path: str) -> None:
        """Helper to upload a local file to the configured blob container."""
        try:
            blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
            with open(file_path, "rb") as data:
                blob_client.upload_blob(data, overwrite=True)
            logging.info(f"Uploaded {blob_name} to Blob Storage")
        except Exception as upload_error:
            logging.error(f"Failed to upload {blob_name}: {upload_error}")

    # Upload the JSON topology and both diagrams
    upload_file(json_file_name, json_file_path)
    upload_file(diagram_file_name_mld, diagram_file_path_mld)
    upload_file(diagram_file_name_hld, diagram_file_path_hld)

    logging.info("DrawTrigger function execution completed successfully")