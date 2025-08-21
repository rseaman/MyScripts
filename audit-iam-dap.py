#!/usr/bin/env python3

"""
This script is used to audit IAM users for directly attached policies.
It will create a new IAM group for each policy and add the user to the group.
"""

import boto3
from botocore.exceptions import ClientError
import re


def get_user_direct_policies(iam_client, username):
    """Get directly attached policies for a user."""
    try:
        attached_policies = iam_client.list_attached_user_policies(UserName=username)[
            "AttachedPolicies"
        ]
        return attached_policies
    except ClientError as e:
        print(f"❌ Error getting policies for user {username}: {e}")
        return []


def sanitize_group_name(policy_name):
    """Convert policy name to valid IAM group name."""
    # Remove special characters and replace with hyphens
    sanitized = re.sub(r"[^a-zA-Z0-9+=,.@_-]", "-", policy_name)
    # Ensure it starts with a letter or number
    if sanitized and not sanitized[0].isalnum():
        sanitized = "group-" + sanitized
    # Limit length to 128 characters
    return sanitized[:128]


def create_iam_group(iam_client, group_name):
    """Create an IAM group."""
    try:
        iam_client.create_group(GroupName=group_name)
        print(f"✅ Created IAM group: {group_name}")
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            print(f"ℹ️  Group {group_name} already exists")
            return True
        else:
            print(f"❌ Error creating group {group_name}: {e}")
            return False


def attach_policy_to_group(iam_client, group_name, policy_arn):
    """Attach a policy to an IAM group."""
    try:
        iam_client.attach_group_policy(GroupName=group_name, PolicyArn=policy_arn)
        print(f"✅ Attached policy {policy_arn} to group {group_name}")
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            print(f"ℹ️  Policy {policy_arn} already attached to group {group_name}")
            return True
        else:
            print(f"❌ Error attaching policy {policy_arn} to group {group_name}: {e}")
            return False


def add_user_to_group(iam_client, username, group_name):
    """Add a user to an IAM group."""
    try:
        iam_client.add_user_to_group(GroupName=group_name, UserName=username)
        print(f"✅ Added user {username} to group {group_name}")
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityAlreadyExists":
            print(f"ℹ️  User {username} already in group {group_name}")
            return True
        else:
            print(f"❌ Error adding user {username} to group {group_name}: {e}")
            return False


def detach_policy_from_user(iam_client, username, policy_arn):
    """Detach a policy from a user."""
    try:
        iam_client.detach_user_policy(UserName=username, PolicyArn=policy_arn)
        print(f"✅ Detached policy {policy_arn} from user {username}")
        return True
    except ClientError as e:
        print(f"❌ Error detaching policy {policy_arn} from user {username}: {e}")
        return False


def get_existing_groups(iam_client):
    """Get list of existing IAM groups."""
    try:
        groups = iam_client.list_groups()["Groups"]
        return {group["GroupName"] for group in groups}
    except ClientError as e:
        print(f"❌ Error listing IAM groups: {e}")
        return set()


def create_unique_groups(iam_client, unique_policies, existing_groups):
    """Create unique groups for policies, checking for existing groups first."""
    created_groups = {}

    print("\n🔍 Checking for existing groups and creating new ones...")

    for policy_name in sorted(unique_policies):
        proposed_group_name = sanitize_group_name(f"{policy_name}-group")

        # Check if group already exists
        if proposed_group_name in existing_groups:
            print(f"⚠️  Group '{proposed_group_name}' already exists")
            if get_user_confirmation(
                f"Use existing group '{proposed_group_name}' for policy '{policy_name}'?"
            ):
                created_groups[policy_name] = proposed_group_name
                print(f"✅ Using existing group: {proposed_group_name}")
            else:
                # Generate alternative name
                counter = 1
                while f"{proposed_group_name}-{counter}" in existing_groups:
                    counter += 1
                alternative_name = f"{proposed_group_name}-{counter}"
                if get_user_confirmation(
                    f"Create new group '{alternative_name}' for policy '{policy_name}'?"
                ):
                    if create_iam_group(iam_client, alternative_name):
                        created_groups[policy_name] = alternative_name
                        existing_groups.add(alternative_name)
                else:
                    print(f"⏭️  Skipped creating group for policy '{policy_name}'")
        else:
            # Group doesn't exist, create it
            if get_user_confirmation(
                f"Create group '{proposed_group_name}' for policy '{policy_name}'?"
            ):
                if create_iam_group(iam_client, proposed_group_name):
                    created_groups[policy_name] = proposed_group_name
                    existing_groups.add(proposed_group_name)
            else:
                print(f"⏭️  Skipped creating group for policy '{policy_name}'")

    return created_groups


def get_user_confirmation(prompt):
    """Get user confirmation for an action."""
    while True:
        response = input(f"{prompt} (y/n): ").lower().strip()
        if response in ["y", "yes"]:
            return True
        elif response in ["n", "no"]:
            return False
        else:
            print("Please enter 'y' or 'n'")


def process_user_policies_with_groups(iam_client, user_data, created_groups):
    """Process policies for a single user using pre-created groups."""
    username = user_data["username"]
    attached_policies = user_data["attached_policies"]

    print(f"\n🔧 Processing user: {username}")
    print("=" * 50)

    # Process attached policies
    for policy in attached_policies:
        policy_name = policy["PolicyName"]
        policy_arn = policy["PolicyArn"]

        # Check if we have a group for this policy
        if policy_name not in created_groups:
            print(f"⚠️  No group created for policy '{policy_name}', skipping...")
            continue

        group_name = created_groups[policy_name]

        print(f"\n📎 Policy: {policy_name}")
        print(f"   ARN: {policy_arn}")
        print(f"   Group: {group_name}")

        # Attach policy to group (if not already attached)
        if attach_policy_to_group(iam_client, group_name, policy_arn):
            # Add user to group
            if add_user_to_group(iam_client, username, group_name):
                # Detach policy from user
                if get_user_confirmation(
                    f"Remove direct policy attachment from user {username}?"
                ):
                    detach_policy_from_user(iam_client, username, policy_arn)
                else:
                    print(
                        f"⚠️  Skipped removing direct policy attachment for {username}"
                    )
            else:
                print(f"❌ Failed to add user to group, skipping policy detachment")
        else:
            print(f"❌ Failed to attach policy to group, skipping user addition")


def audit_iam_users():
    """Audit IAM users for directly attached policies."""
    iam_client = boto3.client("iam")

    try:
        users = iam_client.list_users()["Users"]
        users_with_direct_policies = []
        unique_policies = set()

        print("🔍 Scanning IAM users for direct policy attachments...")

        for user in users:
            username = user["UserName"]
            attached_policies = get_user_direct_policies(iam_client, username)

            if attached_policies:
                users_with_direct_policies.append(
                    {
                        "username": username,
                        "attached_policies": attached_policies,
                    }
                )
                # Collect unique policy names
                for policy in attached_policies:
                    unique_policies.add(policy["PolicyName"])

        if users_with_direct_policies:
            print("\n⚠️  Users with directly attached policies:")
            print("=====================================")
            for user in users_with_direct_policies:
                print(f"\n👤 User: {user['username']}")
                print("  📎 Attached Policies:")
                for policy in user["attached_policies"]:
                    print(f"    • {policy['PolicyName']}")

            print(
                f"\n📊 Summary: Found {len(users_with_direct_policies)} users with direct policy attachments"
            )
            print(f"📋 Unique policies to process: {len(unique_policies)}")
            print("Unique policies:", ", ".join(sorted(unique_policies)))

            if get_user_confirmation(
                "Would you like to process these users and create IAM groups?"
            ):
                print("\n🚀 Starting interactive policy migration...")
                # First, check for existing groups and create unique groups
                existing_groups = get_existing_groups(iam_client)
                created_groups = create_unique_groups(
                    iam_client, unique_policies, existing_groups
                )

                # Then process each user
                for user_data in users_with_direct_policies:
                    process_user_policies_with_groups(
                        iam_client, user_data, created_groups
                    )
                    print("\n" + "=" * 60 + "\n")

                print("✅ Policy migration process completed!")
            else:
                print("⏭️  Skipped policy migration")
        else:
            print("✅ No users found with directly attached policies.")

    except ClientError as e:
        print(f"❌ Error listing IAM users: {e}")


if __name__ == "__main__":
    audit_iam_users()
