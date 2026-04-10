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

### 1. Setup Google Cloud Project

Run the script by providing your Project ID and (optionally) a file containing allowed models:

```bash
python setup_gcp.py --project_id YOUR_PROJECT_ID --allowed_models_file allowed_models.txt
```

This will create a `credentials.json` file in your current directory. **Do not commit this file to version control.**

### 2. Configure Environment

Copy the example environment file and update it with your project details:

```bash
cp example.env .env
```

Edit `.env` and set `GOOGLE_CLOUD_PROJECT` to your Project ID.

## What the setup script does:

1.  **Enables APIs**:
    - `iam.googleapis.com`
    - `aiplatform.googleapis.com`
    - `cloudresourcemanager.googleapis.com`
    - `serviceusage.googleapis.com`
2.  **Updates Org Policies** (if the project is in an organization):
    - Disables `iam.disableServiceAccountKeyCreation` (allows key creation).
    - Disables `iam-managed.disableServiceAccountKeyCreation` (allows key creation).
    - Allows all for `iam.allowServiceAccountCredentialLifetimeExtension`.
    - (Optional) Restricts Vertex AI models via `vertexai.allowedModels` if the `--allowed_models_file` flag is used. The script will read the list of models from the provided text file.

3.  **Creates a Custom Role**: `dlai_lab_runner` with permissions for Vertex AI and IAM impersonation.
4.  **Creates a Service Account**: `dlai-lab-sa`.
5.  **Assigns the Custom Role** to the service account.
6.  **Downloads Service Account Key**: Saves as `credentials.json`.

## Helper Utility

The `helpers.py` file provides an `authenticate()` function that can be used in your notebooks to automatically load credentials from `credentials.json` or environment variables and set up the Google Cloud environment.
