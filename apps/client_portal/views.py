"""Views for the Client Portal (F-1.4)."""

import json
from datetime import timedelta

from django.db.models import Count, Max, Q, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.approvals import comments as comment_service
from apps.approvals import services as approval_services
from apps.approvals.models import ApprovalAction
from apps.composer.models import PlatformPost, Post
from apps.credentials.models import PlatformCredential
from apps.onboarding.models import ConnectionLink
from apps.social_accounts.models import SocialAccount
from apps.social_accounts.views import _get_configured_platforms, _get_provider_for_platform

from .decorators import portal_auth_required
from .services import create_portal_session, verify_magic_link

# ---------------------------------------------------------------------------
# Magic Link Entry
# ---------------------------------------------------------------------------


def magic_link_entry(request, token):
    """Verify magic link token, create portal session, redirect to dashboard."""
    user, workspace, is_valid = verify_magic_link(token)

    if not is_valid:
        return redirect("client_portal:magic_link_expired")

    create_portal_session(request, user, workspace)
    return redirect("client_portal:dashboard")


def magic_link_expired(request):
    """Show page for expired or invalid magic links."""
    return render(request, "client_portal/magic_link_expired.html")


# ---------------------------------------------------------------------------
# Portal Dashboard
# ---------------------------------------------------------------------------


@portal_auth_required
@require_GET
def portal_dashboard(request):
    """Portal landing page with summary counts and quick links."""
    workspace = request.portal_workspace

    connected_accounts = SocialAccount.objects.for_workspace(workspace.id).filter(
        connection_status=SocialAccount.ConnectionStatus.CONNECTED
    )
    social_summary = connected_accounts.aggregate(
        account_count=Count("id"),
        follower_count=Sum("follower_count"),
    )

    pending_count = (
        Post.objects.for_workspace(workspace.id)
        .filter(platform_posts__status=PlatformPost.Status.PENDING_CLIENT)
        .distinct()
        .count()
    )

    recent_published = (
        Post.objects.for_workspace(workspace.id)
        .filter(platform_posts__status=PlatformPost.Status.PUBLISHED)
        .distinct()
        .order_by("-published_at")[:5]
    )

    my_actions = ApprovalAction.objects.filter(
        user=request.user,
        post__workspace=workspace,
    ).order_by("-created_at")[:5]

    return render(
        request,
        "client_portal/dashboard.html",
        {
            "workspace": workspace,
            "pending_count": pending_count,
            "recent_published": recent_published,
            "my_actions": my_actions,
            "connected_accounts_count": social_summary["account_count"] or 0,
            "total_followers": social_summary["follower_count"] or 0,
        },
    )


# ---------------------------------------------------------------------------
# Portal Approval Queue
# ---------------------------------------------------------------------------


@portal_auth_required
@require_GET
def portal_approval_queue(request):
    """Posts pending client approval."""
    workspace = request.portal_workspace

    posts = (
        Post.objects.for_workspace(workspace.id)
        .filter(platform_posts__status="pending_client")
        .distinct()
        .select_related("author")
        .prefetch_related(
            "platform_posts__social_account",
            "media_attachments__media_asset",
        )
        .order_by("scheduled_at", "-created_at")
    )

    # Annotate each post with visible comments (external only for clients)
    posts = list(posts)
    for post in posts:
        post.visible_comments = list(comment_service.get_comments_for_post(post, request.user))

    return render(
        request,
        "client_portal/approval_queue.html",
        {
            "workspace": workspace,
            "posts": posts,
        },
    )


@portal_auth_required
@require_POST
def portal_approve(request, post_id):
    """Approve a post from the client portal."""
    workspace = request.portal_workspace
    post = get_object_or_404(Post, id=post_id, workspace=workspace)
    if not post.platform_posts.filter(status="pending_client").exists():
        raise Http404
    comment_text = request.POST.get("comment", "")

    try:
        approval_services.approve_post(post, request.user, workspace, comment_text)
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    if request.htmx:
        return HttpResponse(
            status=204,
            headers={"HX-Trigger": json.dumps({"portalAction": {"postId": str(post.id), "action": "approved"}})},
        )
    return redirect("client_portal:approval_queue")


@portal_auth_required
@require_POST
def portal_request_changes(request, post_id):
    """Request changes on a post from the client portal."""
    workspace = request.portal_workspace
    post = get_object_or_404(Post, id=post_id, workspace=workspace)
    if not post.platform_posts.filter(status="pending_client").exists():
        raise Http404
    comment_text = request.POST.get("comment", "")

    try:
        approval_services.request_changes(post, request.user, workspace, comment_text)
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    if request.htmx:
        return HttpResponse(
            status=204,
            headers={
                "HX-Trigger": json.dumps({"portalAction": {"postId": str(post.id), "action": "changes_requested"}})
            },
        )
    return redirect("client_portal:approval_queue")


@portal_auth_required
@require_POST
def portal_reject(request, post_id):
    """Reject a post from the client portal."""
    workspace = request.portal_workspace
    post = get_object_or_404(Post, id=post_id, workspace=workspace)
    if not post.platform_posts.filter(status="pending_client").exists():
        raise Http404
    comment_text = request.POST.get("comment", "")

    try:
        approval_services.reject_post(post, request.user, workspace, comment_text)
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    if request.htmx:
        return HttpResponse(
            status=204,
            headers={"HX-Trigger": json.dumps({"portalAction": {"postId": str(post.id), "action": "rejected"}})},
        )
    return redirect("client_portal:approval_queue")


# ---------------------------------------------------------------------------
# Published Content
# ---------------------------------------------------------------------------


@portal_auth_required
@require_GET
def portal_published(request):
    """Chronological list of published posts."""
    workspace = request.portal_workspace

    posts = (
        Post.objects.for_workspace(workspace.id)
        .filter(platform_posts__status="published")
        .distinct()
        .select_related("author")
        .prefetch_related("platform_posts__social_account", "media_attachments__media_asset")
        .order_by("-published_at")
    )

    return render(
        request,
        "client_portal/published.html",
        {
            "workspace": workspace,
            "posts": posts,
        },
    )


# ---------------------------------------------------------------------------
# Activity Log
# ---------------------------------------------------------------------------


@portal_auth_required
@require_GET
def portal_activity(request):
    """Client's own approval actions."""
    workspace = request.portal_workspace

    actions = (
        ApprovalAction.objects.filter(
            user=request.user,
            post__workspace=workspace,
        )
        .select_related("post")
        .order_by("-created_at")
    )

    return render(
        request,
        "client_portal/activity.html",
        {
            "workspace": workspace,
            "actions": actions,
        },
    )


# ---------------------------------------------------------------------------
# Social Accounts
# ---------------------------------------------------------------------------


@portal_auth_required
@require_GET
def portal_socials(request):
    """Client-facing account connections and connected channel health."""
    workspace = request.portal_workspace

    accounts = (
        SocialAccount.objects.for_workspace(workspace.id)
        .annotate(
            published_count=Count(
                "platform_posts",
                filter=Q(platform_posts__status=PlatformPost.Status.PUBLISHED),
            ),
            scheduled_count=Count(
                "platform_posts",
                filter=Q(platform_posts__status=PlatformPost.Status.SCHEDULED),
            ),
            last_published_at=Max(
                "platform_posts__published_at",
                filter=Q(platform_posts__status=PlatformPost.Status.PUBLISHED),
            ),
        )
        .order_by("platform", "account_name")
    )
    configured_platforms = _get_configured_platforms(workspace.organization_id)
    connection_link = _get_or_create_portal_connection_link(workspace, request.user)

    return render(
        request,
        "client_portal/socials.html",
        {
            "workspace": workspace,
            "accounts": accounts,
            "configured_platforms": configured_platforms,
            "connection_link": connection_link,
            "platform_choices": PlatformCredential.Platform.choices,
        },
    )


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@portal_auth_required
@require_GET
def portal_reports(request):
    """Client-facing social performance summary."""
    workspace = request.portal_workspace
    report = _build_portal_report(workspace)

    return render(
        request,
        "client_portal/reports.html",
        {
            "workspace": workspace,
            **report,
        },
    )


def _get_or_create_portal_connection_link(workspace, user):
    """Return an active connection link for a portal client."""
    now = timezone.now()
    link = (
        ConnectionLink.objects.filter(
            workspace=workspace,
            created_by=user,
            revoked_at__isnull=True,
            expires_at__gt=now,
        )
        .order_by("-created_at")
        .first()
    )
    if link:
        return link

    return ConnectionLink.objects.create(
        workspace=workspace,
        created_by=user,
        expires_at=now + timedelta(days=30),
    )


def _build_portal_report(workspace):
    now = timezone.now()
    since = now - timedelta(days=30)

    accounts = list(
        SocialAccount.objects.for_workspace(workspace.id)
        .annotate(
            published_count=Count(
                "platform_posts",
                filter=Q(platform_posts__status=PlatformPost.Status.PUBLISHED),
            ),
            published_count_30d=Count(
                "platform_posts",
                filter=Q(
                    platform_posts__status=PlatformPost.Status.PUBLISHED,
                    platform_posts__published_at__gte=since,
                ),
            ),
            scheduled_count=Count(
                "platform_posts",
                filter=Q(platform_posts__status=PlatformPost.Status.SCHEDULED),
            ),
            pending_count=Count(
                "platform_posts",
                filter=Q(platform_posts__status=PlatformPost.Status.PENDING_CLIENT),
            ),
            last_published_at=Max(
                "platform_posts__published_at",
                filter=Q(platform_posts__status=PlatformPost.Status.PUBLISHED),
            ),
        )
        .order_by("platform", "account_name")
    )

    platform_posts = list(
        PlatformPost.objects.filter(
            post__workspace=workspace,
            status=PlatformPost.Status.PUBLISHED,
        )
        .select_related("post", "social_account")
        .order_by("-published_at")[:12]
    )

    metric_totals = {
        "impressions": 0,
        "engagements": 0,
        "likes": 0,
        "comments": 0,
        "shares": 0,
        "clicks": 0,
    }
    recent_posts = []
    for platform_post in platform_posts:
        metrics = _safe_fetch_post_metrics(platform_post)
        if metrics:
            for key in metric_totals:
                metric_totals[key] += getattr(metrics, key, 0) or 0

        recent_posts.append(
            {
                "platform_post": platform_post,
                "metrics": metrics,
            }
        )

    published_30d = PlatformPost.objects.filter(
        post__workspace=workspace,
        status=PlatformPost.Status.PUBLISHED,
        published_at__gte=since,
    ).count()
    scheduled_count = PlatformPost.objects.filter(
        post__workspace=workspace,
        status=PlatformPost.Status.SCHEDULED,
    ).count()
    pending_count = PlatformPost.objects.filter(
        post__workspace=workspace,
        status=PlatformPost.Status.PENDING_CLIENT,
    ).count()
    total_followers = sum(account.follower_count or 0 for account in accounts)

    return {
        "accounts": accounts,
        "recent_posts": recent_posts,
        "metric_totals": metric_totals,
        "published_30d": published_30d,
        "scheduled_count": scheduled_count,
        "pending_count": pending_count,
        "total_followers": total_followers,
        "connected_accounts_count": sum(
            1 for account in accounts if account.connection_status == SocialAccount.ConnectionStatus.CONNECTED
        ),
    }


def _safe_fetch_post_metrics(platform_post):
    account = platform_post.social_account
    if not platform_post.platform_post_id or not account.oauth_access_token:
        return None

    extra_credentials = {}
    if account.platform == "mastodon" and account.instance_url:
        extra_credentials["instance_url"] = account.instance_url
    elif account.platform == "bluesky" and account.instance_url:
        extra_credentials["pds_url"] = account.instance_url

    try:
        provider = _get_provider_for_platform(
            account.platform,
            account.workspace.organization_id,
            **extra_credentials,
        )
        return provider.get_post_metrics(account.oauth_access_token, platform_post.platform_post_id)
    except NotImplementedError:
        return None
    except Exception:
        return None
