# GCP Project Setup for DLAI Labs

This script automates the setup of a Google Cloud Project for DLAI labs, including enabling APIs, updating organization policies, creating a custom IAM role, and setting up a service account with credentials.

## Prerequisites

1.  **Google Cloud Project**: You must have an existing Google Cloud Project.
2.  **Authentication**: Ensure you are authenticated with the Google Cloud CLI:
    ```bash
    gcloud auth application-default login
    ```
    *Note: The account used must have sufficient permissions to modify Org Policies (Org Policy Administrator), IAM Roles (Role Administrator), and Service Accounts.*

## Installation

Install the required Python libraries:

```bash
pip install -r requirements.txt
```

## Usage

Run the script by providing your Project ID:

```bash
python setup_gcp.py --project_id YOUR_PROJECT_ID
```

## What the script does:

1.  **Enables APIs**:
    - `iam.googleapis.com`
    - `aiplatform.googleapis.com`
    - `cloudresourcemanager.googleapis.com`
    - `serviceusage.googleapis.com`
2.  **Updates Org Policies**:
    - Disables `iam.disableServiceAccountKeyCreation` (allows key creation).
    - Disables `iam-managed.disableServiceAccountKeyCreation` (allows key creation).
    - Allows all for `iam.allowServiceAccountCredentialLifetimeExtension`.
3.  **Creates a Custom Role**: `dlai_lab_runner` with minimal permissions for Vertex AI and IAM.
4.  **Creates a Service Account**: `dlai-lab-sa`.
5.  **Assigns the Custom Role** to the service account.
6.  **Downloads Service Account Key**: Saves as `credentials.json` in the current directory.
