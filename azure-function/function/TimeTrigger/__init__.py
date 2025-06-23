import os
import json
import logging
from datetime import datetime
import azure.functions as func

from azure.identity import DefaultAzureCredential
from azure.mgmt.network import NetworkManagementClient
from azure.storage.blob import BlobServiceClient

from .azure_query import get_vnet_topology
from .MLD import create_drawio_vnet_hub_and_spokes_diagram_MLD
from .HLD import create_drawio_vnet_hub_and_spokes_diagram_HLD

def main(mytimer: func.TimerRequest) -> None:
    logging.info('Function triggered!')

    # Get current UTC timestamp
    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")  

    # Step 1: Query Azure for network topology
    topology_data = get_vnet_topology()
    json_data = json.dumps(topology_data, indent=2)

    # Save JSON to /tmp/
    json_file_name = f"{timestamp}_network_topology.json"
    json_file_path = f"/tmp/{json_file_name}"
    with open(json_file_path, "w") as json_file:
        json_file.write(json_data)
    logging.info(f"Saved topology JSON to {json_file_path}")

    # Step 2: Generate MLD diagram
    diagram_file_name_MLD = f"{timestamp}_network_diagram_MLD.drawio"
    diagram_file_path_MLD = f"/tmp/{diagram_file_name_MLD}"
    create_drawio_vnet_hub_and_spokes_diagram_MLD(
        output_filename=diagram_file_path_MLD,
        json_input_file=json_file_path
    )
    logging.info(f"Generated MLD diagram at {diagram_file_path_MLD}")

    # Step 3: Generate HLD diagram
    diagram_file_name_HLD = f"{timestamp}_network_diagram_HLD.drawio"
    diagram_file_path_HLD = f"/tmp/{diagram_file_name_HLD}"
    create_drawio_vnet_hub_and_spokes_diagram_HLD(
        output_filename=diagram_file_path_HLD,
        json_input_file=json_file_path
    )
    logging.info(f"Generated HLD diagram at {diagram_file_path_HLD}")

    # Step 4: Upload files to Blob Storage
    credential = DefaultAzureCredential()
    account_url = os.environ["DRAWING_STORAGE_URL"]
    container_name = os.environ["DRAWING_CONTAINER_NAME"]
    blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)

    # Upload JSON
    blob_client_json = blob_service_client.get_blob_client(container=container_name, blob=json_file_name)
    with open(json_file_path, "rb") as data:
        blob_client_json.upload_blob(data, overwrite=True)
    logging.info(f"Uploaded {json_file_name} to Blob Storage.")

    # Upload MLD diagram
    blob_client_diagram_mld = blob_service_client.get_blob_client(container=container_name, blob=diagram_file_name_MLD)
    with open(diagram_file_path_MLD, "rb") as data:
        blob_client_diagram_mld.upload_blob(data, overwrite=True)
    logging.info(f"Uploaded {diagram_file_name_MLD} to Blob Storage.")

    # Upload HLD diagram
    blob_client_diagram_hld = blob_service_client.get_blob_client(container=container_name, blob=diagram_file_name_HLD)
    with open(diagram_file_path_HLD, "rb") as data:
        blob_client_diagram_hld.upload_blob(data, overwrite=True)
    logging.info(f"Uploaded {diagram_file_name_HLD} to Blob Storage.")

    logging.info("Function execution complete.")
