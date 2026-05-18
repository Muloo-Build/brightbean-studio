import pytest
from django.urls import reverse

from apps.members.models import OrgMembership, WorkspaceMembership
from apps.onboarding.models import ConnectionLink
from apps.social_accounts.models import SocialAccount
from apps.workspaces.models import Workspace


@pytest.fixture
def workspace(db, organization):
    return Workspace.objects.create(name="Transnova", organization=organization)


@pytest.fixture
def portal_client(client, user, organization, workspace):
    OrgMembership.objects.create(
        user=user,
        organization=organization,
        org_role=OrgMembership.OrgRole.MEMBER,
    )
    WorkspaceMembership.objects.create(
        user=user,
        workspace=workspace,
        workspace_role=WorkspaceMembership.WorkspaceRole.CLIENT,
    )
    client.force_login(user)
    session = client.session
    session["is_portal_session"] = True
    session["portal_workspace_id"] = str(workspace.id)
    session.save()
    return client


@pytest.mark.django_db
class TestPortalSocialsAndStats:
    def test_socials_page_renders_and_creates_connection_link(self, portal_client, workspace, user):
        SocialAccount.objects.create(
            workspace=workspace,
            platform="instagram",
            account_platform_id="ig-1",
            account_name="Transnova Instagram",
            follower_count=1200,
        )

        response = portal_client.get(reverse("client_portal:socials"))

        assert response.status_code == 200
        assert b"Transnova Instagram" in response.content
        assert ConnectionLink.objects.filter(workspace=workspace, created_by=user).exists()

    def test_reports_page_renders_connected_account_stats(self, portal_client, workspace):
        SocialAccount.objects.create(
            workspace=workspace,
            platform="linkedin_company",
            account_platform_id="li-1",
            account_name="Transnova LinkedIn",
            follower_count=3400,
        )

        response = portal_client.get(reverse("client_portal:reports"))

        assert response.status_code == 200
        assert b"Transnova LinkedIn" in response.content
        assert b"3,400" in response.content
