"""Dashboard page routes."""

from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, render_template

pages_bp = Blueprint("pages", __name__)


def _module_enabled(module_id: str) -> bool:
    """Return whether a dashboard module is enabled.

    Read the module registry from Flask application config and return the
    enabled state for the requested module. Treat a missing or empty registry as
    fully enabled so older installs without ``modules.json`` keep working.

    Args:
        module_id: Stable module identifier from ``modules.json``.

    Returns:
        bool: True when the module is enabled or the registry is unavailable.
    """
    modules = current_app.config.get("MODULES", [])
    if not modules:
        return True
    return any(module.get("id") == module_id and module.get("enabled", False) for module in modules)


@pages_bp.route("/")
def index() -> str:
    """Render the overview page.

    Serve the dashboard landing page that summarizes system activity and status.
    This route only selects the matching template and marks the overview entry as active for navigation state.

    Dependencies:
        Uses Flask's ``render_template`` with ``templates/index.html``.

    Returns:
        str: Rendered HTML for the overview page.
    """
    return render_template("index.html", active_page="overview")


@pages_bp.route("/agents")
def agents_page() -> str:
    """Render the agents page.

    Serve the page that lists and organizes dashboard-managed agents.
    This route passes only the active navigation marker needed by the shared layout.

    Dependencies:
        Uses Flask's ``render_template`` with ``templates/agents.html``.

    Returns:
        str: Rendered HTML for the agents page.
    """
    return render_template("agents.html", active_page="agents")


@pages_bp.route("/coding-agents")
def coding_agents_page() -> str:
    """Render the coding agents page.

    Serve the interface dedicated to coding-agent workflows and status.
    This route only binds the coding-agents template to the standard sidebar active state.

    Dependencies:
        Uses Flask's ``render_template`` with ``templates/coding-agents.html``.

    Returns:
        str: Rendered HTML for the coding agents page.
    """
    if not _module_enabled("coding_agents"):
        return render_template("module-disabled.html", active_page="coding-agents", module_name="Coding Agents")
    return render_template("coding-agents.html", active_page="coding-agents")


@pages_bp.route("/r-memory")
def r_memory_page() -> str:
    """Render the R-Memory page.

    Serve the R-Memory management page used for SSoT and compression workflows.
    This route simply activates the matching sidebar entry and renders the corresponding template.

    Dependencies:
        Uses Flask's ``render_template`` with ``templates/r-memory.html``.

    Returns:
        str: Rendered HTML for the R-Memory page.
    """
    return render_template("r-memory.html", active_page="r-memory")


@pages_bp.route("/projects")
def projects_page() -> str:
    """Render the projects page.

    Serve the project-management interface for viewing boards, tasks, and project state.
    This route does not load project data directly and leaves API hydration to the frontend.

    Dependencies:
        Uses Flask's ``render_template`` with ``templates/projects.html``.

    Returns:
        str: Rendered HTML for the projects page.
    """
    if not _module_enabled("projects"):
        return render_template("module-disabled.html", active_page="projects", module_name="Projects")
    return render_template("projects.html", active_page="projects")


@pages_bp.route("/chatbots")
def chatbots_page() -> str:
    """Render the chatbots page.

    Serve the chatbot builder and management interface exposed by the dashboard.
    This route only selects the page template and sets the active navigation item.

    Dependencies:
        Uses Flask's ``render_template`` with ``templates/chatbots.html``.

    Returns:
        str: Rendered HTML for the chatbots page.
    """
    if not _module_enabled("chatbots"):
        return render_template("module-disabled.html", active_page="chatbots", module_name="Chatbots")
    return render_template("chatbots.html", active_page="chatbots")


@pages_bp.route("/tribes")
def tribes_page() -> str:
    """Render the tribes page.

    Serve the tribes page for community and membership workflows.
    This route keeps the response minimal by delegating all display details to the Jinja template.

    Dependencies:
        Uses Flask's ``render_template`` with ``templates/tribes.html``.

    Returns:
        str: Rendered HTML for the tribes page.
    """
    if not _module_enabled("tribes"):
        return render_template("module-disabled.html", active_page="tribes", module_name="Tribes")
    return render_template("tribes.html", active_page="tribes")


@pages_bp.route("/bounties")
def bounties_page() -> str:
    """Render the bounties page.

    Serve the bounty board page for listing and managing work items with rewards.
    This route only provides the active-page context expected by the shared layout.

    Dependencies:
        Uses Flask's ``render_template`` with ``templates/bounties.html``.

    Returns:
        str: Rendered HTML for the bounties page.
    """
    if not _module_enabled("bounties"):
        return render_template("module-disabled.html", active_page="bounties", module_name="Bounties")
    return render_template("bounties.html", active_page="bounties")


@pages_bp.route("/protocol-store")
def protocol_store_page() -> str:
    """Render the protocol store page.

    Load the dashboard config when present and pass it into the protocol store template.
    This route tolerates unreadable config content by falling back to an empty mapping instead of failing the page render.

    Dependencies:
        Uses ``Path`` and ``json`` to read ``config.json`` and Flask's ``render_template``.

    Returns:
        str: Rendered HTML for the protocol store page.
    """
    if not _module_enabled("protocol_store"):
        return render_template("module-disabled.html", active_page="protocol-store", module_name="Protocol Store")
    cfg = {}
    cfg_path = Path(__file__).resolve().parent.parent / "config.json"
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text())
        except Exception:
            pass
    return render_template("protocol-store.html", active_page="protocol-store", config=cfg)


@pages_bp.route("/docs")
def docs_page() -> str:
    """Render the docs page.

    Resolve the configured GitBook URL and inject it into the documentation page.
    This route falls back to the default ResonantOS docs URL when the app config does not override it.

    Dependencies:
        Uses Flask's ``current_app`` config and ``render_template`` with ``templates/docs.html``.

    Returns:
        str: Rendered HTML for the docs page.
    """
    gitbook_url = current_app.config.get("GITBOOK_URL", "https://resonantos.gitbook.io/resonantos-docs/")
    return render_template("docs.html", active_page="docs", gitbook_url=gitbook_url)


@pages_bp.route("/license")
def license_page() -> str:
    """Render the license page.

    Serve the dashboard license page for reviewing the current agreement text.
    This route only marks the active navigation state and defers content rendering to the template.

    Dependencies:
        Uses Flask's ``render_template`` with ``templates/license.html``.

    Returns:
        str: Rendered HTML for the license page.
    """
    return render_template("license.html", active_page="license")


@pages_bp.route("/setup")
def setup_page() -> str:
    """Render the setup page.

    Serve the setup instructions and onboarding page for local dashboard configuration.
    This route only provides the navigation context consumed by the base layout.

    Dependencies:
        Uses Flask's ``render_template`` with ``templates/setup.html``.

    Returns:
        str: Rendered HTML for the setup page.
    """
    return render_template("setup.html", active_page="setup")


@pages_bp.route("/todo")
def todo_page() -> str:
    """Render the todo page.

    Serve the page dedicated to general task tracking in the dashboard.
    This route keeps the response static and leaves data retrieval to frontend API calls.

    Dependencies:
        Uses Flask's ``render_template`` with ``templates/todo.html``.

    Returns:
        str: Rendered HTML for the todo page.
    """
    if not _module_enabled("todo"):
        return render_template("module-disabled.html", active_page="todo", module_name="Todo")
    return render_template("todo.html", active_page="todo")


@pages_bp.route("/intelligence")
def intelligence_page() -> str:
    """Render the intelligence page.

    Serve the intelligence page used for analysis-oriented dashboard views.
    This route only selects the matching template and sets the sidebar highlight.

    Dependencies:
        Uses Flask's ``render_template`` with ``templates/intelligence.html``.

    Returns:
        str: Rendered HTML for the intelligence page.
    """
    return render_template("intelligence.html", active_page="intelligence")


@pages_bp.route("/api/intelligence")
def api_intelligence() -> Response:
    """Return intelligence scan data.

    Serve a stub intelligence payload for the dashboard intelligence page.
    This route does not parse scan artifacts yet and always returns an empty
    intelligence mapping with no last-updated timestamp so the frontend can
    load without a 404.

    Dependencies:
        Uses Flask's ``jsonify`` to serialize the API response.

    Returns:
        JSON response with ``success``, ``intelligence``, and ``lastUpdated``.
        Returns HTTP 200.
    """
    return jsonify({"success": True, "intelligence": {}, "lastUpdated": None})


@pages_bp.route("/memory-bridge")
def memory_bridge_page() -> str:
    """Render the memory bridge page.

    Reuse the settings template while preselecting the memory-bridge tab for the user.
    This route is a page alias that maps a dedicated URL onto the shared settings view.

    Dependencies:
        Uses Flask's ``render_template`` with ``templates/settings.html``.

    Returns:
        str: Rendered HTML for the settings page with the memory-bridge tab selected.
    """
    return render_template("settings.html", active_page="settings", settings_tab="memory-bridge")


@pages_bp.route("/settings")
def settings_page() -> str:
    """Render the settings page.

    Serve the main settings view for dashboard configuration and system controls.
    This route renders the shared settings template without forcing a specific sub-tab.

    Dependencies:
        Uses Flask's ``render_template`` with ``templates/settings.html``.

    Returns:
        str: Rendered HTML for the settings page.
    """
    return render_template("settings.html", active_page="settings")


@pages_bp.route("/ssot")
def ssot_page() -> str:
    """Render the SSoT page.

    Serve the Single Source of Truth browser and management page.
    This route only connects the page URL to its template and shared navigation state.

    Dependencies:
        Uses Flask's ``render_template`` with ``templates/ssot.html``.

    Returns:
        str: Rendered HTML for the SSoT page.
    """
    return render_template("ssot.html", active_page="ssot")


@pages_bp.route("/shield")
def shield_page() -> str:
    """Render the shield page.

    Serve the dashboard security page that summarizes Shield-related status and controls.
    This route leaves all live data loading to the frontend and only renders the shell template.

    Dependencies:
        Uses Flask's ``render_template`` with ``templates/shield.html``.

    Returns:
        str: Rendered HTML for the shield page.
    """
    return render_template("shield.html", active_page="shield")


@pages_bp.route("/policy-graph")
def policy_graph() -> str:
    """Render the policy graph page.

    Serve the policy graph visualization page for exploring system rules and flows.
    This route maps the URL to its template and activates the corresponding navigation entry.

    Dependencies:
        Uses Flask's ``render_template`` with ``templates/policy-graph.html``.

    Returns:
        str: Rendered HTML for the policy graph page.
    """
    return render_template("policy-graph.html", active_page="policy-graph")
