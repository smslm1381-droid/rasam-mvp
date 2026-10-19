"""مدیریت سازمان از مدیریت کل محصول جداست؛ مجوز در سرویس‌ها اعمال می‌شود."""

from fastapi import APIRouter, Request

from organization_portal import http, organizations, permissions, usage
from organization_portal.models import ConnectionInput, Invite, MemberUpdate, NewOrganization, OrganizationUpdate


def routes():
    router = APIRouter(prefix="/api")

    @router.get("/platform/organizations")
    def platform_list(request: Request):
        permissions.platform_admin(http.current(request))
        return request.app.state.store.query("SELECT id,name,active,daily_limit,allowed_hosts,manager_chat_access FROM organizations ORDER BY name LIMIT 500")

    @router.post("/platform/organizations")
    def create(request: Request, body: NewOrganization):
        return organizations.create(request.app.state.store, http.current(request), body.name,
                                    body.manager_email, body.hosts, body.daily_limit)

    @router.patch("/platform/organizations/{org_id}")
    def configure(request: Request, org_id: str, body: OrganizationUpdate):
        return organizations.configure(request.app.state.store, http.current(request), org_id,
                                       body.active, body.daily_limit, body.hosts, body.manager_chat_access)

    @router.get("/organizations/{org_id}/members")
    def members(request: Request, org_id: str):
        return organizations.members(request.app.state.store, http.current(request), org_id)

    @router.post("/organizations/{org_id}/invitations")
    def invite(request: Request, org_id: str, body: Invite):
        return organizations.invite(request.app.state.store, http.current(request), org_id,
                                   body.email, body.role, body.daily_limit, body.sources)

    @router.patch("/organizations/{org_id}/members/{member_id}")
    def update(request: Request, org_id: str, member_id: str, body: MemberUpdate):
        return organizations.update_member(request.app.state.store, http.current(request), org_id,
                                           member_id, body.active, body.daily_limit, body.sources)

    router.include_router(connection_routes())
    return router


def connection_routes():
    router = APIRouter()

    @router.get("/organizations/{org_id}/connection")
    def connection(request: Request, org_id: str):
        return request.app.state.connections.public(http.current(request), org_id)

    @router.post("/organizations/{org_id}/connection/test")
    def test(request: Request, org_id: str, body: ConnectionInput):
        return request.app.state.connections.probe(http.current(request), org_id, body.connection_data())

    @router.put("/organizations/{org_id}/connection")
    def save(request: Request, org_id: str, body: ConnectionInput):
        return request.app.state.connections.save(http.current(request), org_id, body.connection_data())

    @router.get("/organizations/{org_id}/usage")
    def current_usage(request: Request, org_id: str):
        user = http.current(request)
        member = permissions.membership(request.app.state.store, user, org_id)
        return {**usage.summary(request.app.state.store, org_id, user["id"]),
                "member_limit": member["daily_limit"], "organization_limit": member["org_limit"]}

    @router.get("/organizations/{org_id}/audit")
    def audit(request: Request, org_id: str):
        permissions.membership(request.app.state.store, http.current(request), org_id, admin=True)
        return request.app.state.store.query("""SELECT actor_id,action,subject_id,created
            FROM audit_events WHERE org_id=? ORDER BY created DESC,rowid DESC LIMIT 100""", org_id)

    return router
