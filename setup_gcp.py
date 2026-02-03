import argparse
import json
import time

from google.api_core import exceptions
from google.cloud import (
    iam_admin_v1,
    orgpolicy_v2,
    resourcemanager_v3,
    service_usage_v1,
)
from google.iam.v1 import iam_policy_pb2, policy_pb2


def enable_apis(project_id, apis):
    print(f"Enabling APIs: {', '.join(apis)}...")
    client = service_usage_v1.ServiceUsageClient()
    for api in apis:
        operation = client.enable_service(
            service_usage_v1.EnableServiceRequest(
                name=f"projects/{project_id}/services/{api}"
            )
        )
        operation.result()
    print("APIs enabled.")


def update_org_policy_boolean(
    project_id: str, constraint: str, enforce: bool = False
) -> None:
    print(
        f"Updating Org Policy: {constraint} to {'enforce' if enforce else 'allow'}..."
    )
    client = orgpolicy_v2.OrgPolicyClient()
    parent = f"projects/{project_id}"
    policy_name = f"{parent}/policies/{constraint}"

    policy = orgpolicy_v2.Policy(
        name=policy_name,
        spec=orgpolicy_v2.PolicySpec(
            rules=[orgpolicy_v2.PolicySpec.PolicyRule(enforce=enforce)]
        ),
    )

    try:
        client.create_policy(parent=parent, policy=policy)
    except exceptions.AlreadyExists:
        client.update_policy(policy=policy)
    print(f"Updated {constraint}.")


def update_org_policy_list_allow_all(project_id: str, constraint: str):
    print(f"Updating Org Policy: {constraint} to allow all...")
    client = orgpolicy_v2.OrgPolicyClient()
    parent = f"projects/{project_id}"
    policy_name = f"{parent}/policies/{constraint}"

    policy = orgpolicy_v2.Policy(
        name=policy_name,
        spec=orgpolicy_v2.PolicySpec(
            rules=[orgpolicy_v2.PolicySpec.PolicyRule(allow_all=True)]
        ),
    )

    try:
        client.create_policy(parent=parent, policy=policy)
    except exceptions.AlreadyExists:
        client.update_policy(policy=policy)
    print(f"Updated {constraint}.")


def create_custom_role(project_id, role_id, title, permissions):
    print(f"Creating custom role: {role_id}...")
    client = iam_admin_v1.IAMClient()
    parent = f"projects/{project_id}"
    full_role_name = f"{parent}/roles/{role_id}"

    role = iam_admin_v1.Role(
        title=title,
        included_permissions=permissions,
        stage=iam_admin_v1.Role.RoleLaunchStage.GA,
    )

    try:
        request = iam_admin_v1.CreateRoleRequest(
            parent=parent, role_id=role_id, role=role
        )
        response = client.create_role(request=request)
    except exceptions.AlreadyExists:
        print(f"Role {role_id} already exists, updating...")
        request = iam_admin_v1.UpdateRoleRequest(name=full_role_name, role=role)
        response = client.update_role(request=request)

    return response.name


def create_service_account(project_id, account_id, display_name):
    print(f"Creating service account: {account_id}...")
    client = iam_admin_v1.IAMClient()
    parent = f"projects/{project_id}"
    email = f"{account_id}@{project_id}.iam.gserviceaccount.com"

    try:
        request = iam_admin_v1.CreateServiceAccountRequest(
            name=parent,
            account_id=account_id,
            service_account=iam_admin_v1.ServiceAccount(display_name=display_name),
        )
        client.create_service_account(request=request)
    except exceptions.AlreadyExists:
        print(f"Service account {account_id} already exists.")

    return email


def assign_role(project_id: str, email: str, role_name: str) -> None:
    print(f"Assigning role {role_name} to {email}...")
    client = resourcemanager_v3.ProjectsClient()
    resource = f"projects/{project_id}"

    policy = client.get_iam_policy(resource=resource)

    member = f"serviceAccount:{email}"
    role_bound = False

    for binding in policy.bindings:
        if binding.role == role_name:
            if member not in binding.members:
                binding.members.append(member)
            role_bound = True
            break

    if not role_bound:
        policy.bindings.append(policy_pb2.Binding(role=role_name, members=[member]))

    request = iam_policy_pb2.SetIamPolicyRequest(resource=resource, policy=policy)
    client.set_iam_policy(request=request)
    print("Role assigned.")


def create_sa_key(email: str, output_file: str = "credentials.json") -> None:
    print(f"Creating key for {email}...")
    client = iam_admin_v1.IAMClient()
    name = f"projects/-/serviceAccounts/{email}"

    request = iam_admin_v1.CreateServiceAccountKeyRequest(
        name=name,
        private_key_type=iam_admin_v1.ServiceAccountPrivateKeyType.TYPE_GOOGLE_CREDENTIALS_FILE,
    )

    key = client.create_service_account_key(request=request)
    key_data = json.loads(key.private_key_data.decode("utf-8"))

    with open(output_file, "w") as f:
        json.dump(key_data, f, indent=2)

    print(f"Key saved to {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Setup GCP Project for DLAI Lab")
    parser.add_argument("--project_id", required=True, help="Google Cloud Project ID")
    args = parser.parse_args()

    project_id = args.project_id

    # 1. Enable APIs
    apis_to_enable = [
        "iam.googleapis.com",
        "aiplatform.googleapis.com",
        "cloudresourcemanager.googleapis.com",
        "serviceusage.googleapis.com",
    ]
    enable_apis(project_id, apis_to_enable)

    try:
        # 2. Update Org Policies
        # Allow Service Account Key Creation
        update_org_policy_boolean(
            project_id, "iam.disableServiceAccountKeyCreation", enforce=False
        )
        update_org_policy_boolean(
            project_id, "iam-managed.disableServiceAccountKeyCreation", enforce=False
        )

        # Allow Extend credential lifetime
        update_org_policy_list_allow_all(
            project_id, "iam.allowServiceAccountCredentialLifetimeExtension"
        )
    except Exception as e:
        print(f"Warning: Could not update Org Policies: {e}")
        print(
            "Ensure you have 'roles/orgpolicy.policyAdmin' and that the project is in an Organization."
        )

    # 3. Create Custom Role
    role_id = "dlai_lab_runner"
    role_title = "DLAI Lab Runner Role"
    permissions = [
        "aiplatform.endpoints.get",
        "aiplatform.endpoints.predict",
        "iam.serviceAccounts.get",
        "iam.serviceAccounts.getAccessToken",
        "iam.serviceAccounts.getOpenIdToken",
    ]
    role_name = create_custom_role(project_id, role_id, role_title, permissions)

    # 4. Create Service Account
    sa_id = "dlai-lab-sa"
    sa_display_name = "DLAI Lab Service Account"
    sa_email = create_service_account(project_id, sa_id, sa_display_name)

    # 5. Assign Role (Wait a bit for SA to propagate)
    time.sleep(5)
    assign_role(project_id, sa_email, role_name)

    # 6. Create and Download Key
    create_sa_key(sa_email, "credentials.json")


if __name__ == "__main__":
    main()
