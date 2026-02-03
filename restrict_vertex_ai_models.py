# Script to Restrict Quotas for specific Models in vertex AI
# Instructions
# $ python restrict_vertex_ai_models.py -a list-of-models-to-allow (--no-dry-run to set the quotas to 0)

import argparse
import sys
import time

from google.auth import default
from googleapiclient import discovery
from googleapiclient.errors import HttpError


def restrict_vertex_models(project_id, allowed_models, dry_run=True):
    """
    Scans Vertex AI quotas.
    1. Identifies quotas with 'base_model' dimensions.
    2. Skips if an override already exists (preserves manual settings).
    3. If model is NOT in allowed_models, sets limit to 0 (forcing safety checks).
    """

    # 1. Authenticate
    try:
        credentials, _ = default()
        service = discovery.build("serviceusage", "v1beta1", credentials=credentials)
    except Exception as e:
        print(f"Error initializing credentials: {e}")
        sys.exit(1)

    service_name = "aiplatform.googleapis.com"
    parent = f"projects/{project_id}/services/{service_name}"

    print(f"Scanning quotas for project: {project_id}")
    print(f"Allowed Models: {allowed_models}")
    print(f"Dry Run Mode: {dry_run}\n")

    try:
        # List all metrics
        request = service.services().consumerQuotaMetrics().list(parent=parent)

        while request is not None:
            response = request.execute()

            for metric in response.get("metrics", []):
                metric_display = metric.get("displayName", metric.get("name", ""))

                # Iterate through limits in this metric
                for limit in metric.get("consumerQuotaLimits", []):
                    limit_name = limit.get("name", "")

                    # Fetch existing overrides for this specific limit to check for skips
                    existing_overrides = []
                    try:
                        ov_req = (
                            service.services()
                            .consumerQuotaMetrics()
                            .limits()
                            .consumerOverrides()
                            .list(parent=limit_name)
                        )
                        ov_res = ov_req.execute()
                        existing_overrides = ov_res.get("overrides", [])
                    except HttpError:
                        # Some limits don't support overrides or permission issues
                        pass

                    # Iterate through the specific usage buckets (dimensions)
                    for bucket in limit.get("quotaBuckets", []):
                        dims = bucket.get("dimensions", {})

                        # Only care about quotas that differentiate by base_model
                        if "base_model" in dims:
                            model_name = dims["base_model"]

                            # CHECK 1: Does an override already exist for these exact dimensions?
                            if has_existing_override(dims, existing_overrides):
                                print(
                                    f"[Skipping] {model_name} in {metric_display[:40]}... (Manual override exists)"
                                )
                                continue

                            # CHECK 2: Is the model in the allowed list?
                            if model_name not in allowed_models:
                                current_limit = bucket.get("effectiveLimit", -1)

                                # If it's already 0, skip
                                if current_limit == 0:
                                    print(
                                        f"[Skipping] {model_name} in {metric_display[:40]}... (Limit is already 0)"
                                    )
                                    continue

                                print(
                                    f"[Action Required] Block {model_name} in '{metric_display}' | Current Limit: {current_limit}"
                                )

                                if not dry_run:
                                    create_zero_override(service, limit_name, dims)
                                    time.sleep(0.5)  # Avoid rate limits

            # Pagination
            request = (
                service.services()
                .consumerQuotaMetrics()
                .list_next(previous_request=request, previous_response=response)
            )

    except HttpError as err:
        print(f"\nAPI Error: {err}")
        if err.resp.status == 403:
            print(
                "Ensure you have 'Service Usage Consumer' and 'Quota Administrator' roles."
            )
    except Exception as e:
        print(f"\nUnexpected Error: {e}")


def has_existing_override(target_dims, existing_overrides):
    """
    Checks if the target dimensions exactly match any existing override.
    """
    for ov in existing_overrides:
        if ov.get("dimensions") == target_dims:
            return True
    return False


def create_zero_override(service, limit_name, dimensions):
    """
    Creates a new Consumer Override to set the limit to 0.
    Includes force=True to bypass "unsafe reduction" checks.
    """
    override_body = {"overrideValue": "0", "dimensions": dimensions}

    try:
        print(f"   -> Creating override on {limit_name.split('/')[-1]}...")
        service.services().consumerQuotaMetrics().limits().consumerOverrides().create(
            parent=limit_name,
            body=override_body,
            force=True,  # <--- THIS FIXES THE ERROR
        ).execute()
        print("   -> Success.")
    except HttpError as e:
        # Print a clearer error message if it still fails
        print(f"   -> FAILED: {e._get_reason()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Set Vertex AI quotas to 0 for disallowed models."
    )
    parser.add_argument("project_id", help="The Google Cloud Project ID")
    parser.add_argument(
        "--allow",
        "-a",
        required=True,
        help="Comma-separated list of allowed base_models (e.g., gemini-1.5-pro)",
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_true",
        help="Execute the changes. Default is Dry Run.",
    )

    args = parser.parse_args()
    allowed_list = [m.strip() for m in args.allow.split(",")]

    restrict_vertex_models(args.project_id, allowed_list, dry_run=not args.no_dry_run)
