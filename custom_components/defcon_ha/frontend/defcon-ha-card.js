class DefconHaCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = undefined;
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("DEFCON Home card requires an entity");
    }
    this._config = {
      title: "DEFCON Home",
      show_sources: true,
      context_entity: "sensor.defcon_home_context_recommended_defcon",
      ...config,
    };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    const state = this._hass?.states?.[this._config?.entity];
    const count = Array.isArray(state?.attributes?.reasons)
      ? state.attributes.reasons.length
      : 0;
    return Math.max(3, Math.min(9, 3 + count));
  }

  static getStubConfig(hass) {
    const entity = Object.keys(hass?.states || {}).find(
      (id) =>
        id.startsWith("sensor.") &&
        hass.states[id]?.attributes?.engine === "local_deterministic"
    );
    return {
      entity: entity || "sensor.defcon_home_level",
      context_entity: "sensor.defcon_home_context_recommended_defcon",
    };
  }

  _lang() {
    const lang = (this._hass?.language || "en").toLowerCase();
    if (lang.startsWith("fr")) return "fr";
    if (lang.startsWith("de")) return "de";
    return "en";
  }

  _labels() {
    const labels = {
      en: {
        automatic: "Automatic",
        external: "External",
        infrastructure: "Infrastructure",
        context: "Context",
        advisory: "advisory",
        manual: "Manual override",
        reasons: "Active reasons",
        noReasons: "No active alert among configured sources",
        sources: "Sources",
        health: "Source health",
        degraded: "degraded",
        updated: "Evaluated",
      },
      fr: {
        automatic: "Automatique",
        external: "Externe",
        infrastructure: "Infrastructure",
        context: "Contexte",
        advisory: "indicatif",
        manual: "Override manuel",
        reasons: "Raisons actives",
        noReasons: "Aucune alerte active parmi les sources configurées",
        sources: "Sources",
        health: "Santé des sources",
        degraded: "dégradée",
        updated: "Évalué",
      },
      de: {
        automatic: "Automatisch",
        external: "Extern",
        infrastructure: "Infrastruktur",
        context: "Kontext",
        advisory: "indikativ",
        manual: "Manueller Override",
        reasons: "Aktive Gründe",
        noReasons: "Keine aktive Warnung in den konfigurierten Quellen",
        sources: "Quellen",
        health: "Quellenstatus",
        degraded: "eingeschränkt",
        updated: "Ausgewertet",
      },
    };
    return labels[this._lang()];
  }

  _escape(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  _sourceIcon(source) {
    const s = (source || "").toLowerCase();
    if (s.includes("nina")) return "⚠";
    if (s.includes("dwd")) return "☁";
    if (s.includes("hochwasser") || s.includes("pegel")) return "≈";
    if (s.includes("uba")) return "◌";
    if (s.includes("bfs")) return "☢";
    if (s.includes("blitz")) return "ϟ";
    if (s.includes("noaa")) return "☀";
    if (s.includes("incendie")) return "🔥";
    if (s.includes("électrique") || s.includes("electric")) return "⚡";
    if (s.includes("internet")) return "↔";
    return "•";
  }

  _render() {
    if (!this.shadowRoot || !this._config?.entity || !this._hass) return;

    const stateObj = this._hass.states[this._config.entity];
    const labels = this._labels();

    if (!stateObj) {
      this.shadowRoot.innerHTML =
        `<ha-card><div class="error">Entity ${this._escape(this._config.entity)} not found</div></ha-card>`;
      return;
    }

    const attrs = stateObj.attributes || {};
    const level = Number(stateObj.state) || 5;
    const autoLevel = Number(attrs.automatic_level) || level;
    const externalLevel = Number(attrs.external_level) || 5;
    const infrastructureLevel = Number(attrs.infrastructure_level) || 5;
    const color = attrs.color || "var(--primary-color)";
    const reasons = Array.isArray(attrs.reasons) ? attrs.reasons : [];
    const degraded = Array.isArray(attrs.degraded_sources)
      ? attrs.degraded_sources
      : [];
    const sourceEntities = Array.isArray(attrs.source_entities)
      ? attrs.source_entities
      : [];
    const manual = attrs.manual_override || "auto";
    const evaluated = attrs.evaluated_at
      ? new Date(attrs.evaluated_at).toLocaleString(this._hass.language)
      : "";

    const contextObj = this._config.context_entity
      ? this._hass.states[this._config.context_entity]
      : undefined;
    const contextLevel = contextObj ? Number(contextObj.state) : NaN;
    const contextValid =
      contextObj && Number.isFinite(contextLevel) && contextLevel >= 1 && contextLevel <= 5;
    const contextMoreSevere = contextValid && contextLevel < level;
    const contextTitle = contextObj?.attributes?.top_event_title || "";

    const contextHtml = contextValid
      ? `<span
          class="pill context ${contextMoreSevere ? "more-severe" : ""}"
          id="context-pill"
          title="${this._escape(contextTitle)}"
        >${labels.context}: DEFCON ${this._escape(contextLevel)} (${labels.advisory})</span>`
      : "";

    const reasonsHtml = reasons.length
      ? reasons
          .map(
            (reason) => `
          <div class="reason">
            <div class="reason-head">
              <span class="source">${this._escape(this._sourceIcon(reason.source))} ${this._escape(reason.source)}</span>
              <span class="reason-level">DEFCON ${this._escape(reason.level)}</span>
            </div>
            <div class="reason-title">${this._escape(reason.title)}</div>
            ${reason.detail ? `<div class="reason-detail">${this._escape(reason.detail)}</div>` : ""}
          </div>`
          )
          .join("")
      : `<div class="empty">${labels.noReasons}</div>`;

    const degradedHtml = degraded.length
      ? `<div class="health warning"><b>${labels.health}:</b> ${degraded.length} ${labels.degraded}
          <div class="degraded-list">${degraded
            .map(
              (item) =>
                `<code>${this._escape(item.entity_id)} (${this._escape(item.status)})</code>`
            )
            .join("")}</div>
        </div>`
      : `<div class="health ok"><b>${labels.health}:</b> OK</div>`;

    const sourceHtml =
      this._config.show_sources !== false && sourceEntities.length
        ? `<div class="sources"><span>${labels.sources}</span>${sourceEntities
            .map((id) => `<code>${this._escape(id)}</code>`)
            .join("")}</div>`
        : "";

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { overflow: hidden; }
        .top { padding: 18px 20px 16px; color: white; background: ${this._escape(color)}; cursor: pointer; }
        .title { font-size: 14px; font-weight: 600; opacity: .9; }
        .level-row { display: flex; align-items: baseline; gap: 12px; margin-top: 3px; }
        .level { font-size: 38px; line-height: 1.05; font-weight: 750; letter-spacing: -1px; }
        .name { font-size: 18px; font-weight: 600; opacity: .95; }
        .summary { margin-top: 8px; font-size: 14px; line-height: 1.35; opacity: .96; }
        .meta { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
        .pill { border: 1px solid rgba(255,255,255,.45); border-radius: 999px; padding: 4px 8px; font-size: 12px; }
        .pill.context { border-style: dashed; font-weight: 700; cursor: pointer; }
        .pill.context.more-severe { background: rgba(255,255,255,.18); border-style: solid; border-width: 2px; }
        .body { padding: 14px 16px 16px; }
        .section-title { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; opacity: .65; margin-bottom: 8px; }
        .reason { padding: 10px 0; border-top: 1px solid var(--divider-color); }
        .reason:first-of-type { border-top: 0; }
        .reason-head { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
        .source { font-size: 12px; font-weight: 700; opacity: .7; }
        .reason-level { font-size: 11px; font-weight: 700; border-radius: 999px; padding: 3px 7px; background: var(--secondary-background-color); }
        .reason-title { margin-top: 4px; font-weight: 650; line-height: 1.25; }
        .reason-detail { margin-top: 4px; font-size: 13px; line-height: 1.35; opacity: .78; }
        .empty { font-size: 14px; opacity: .72; padding: 4px 0 8px; }
        .health { margin-top: 12px; border-radius: 10px; padding: 10px; font-size: 12px; background: var(--secondary-background-color); }
        .health.warning { border-left: 4px solid var(--warning-color, #f9a825); }
        .health.ok { opacity: .75; }
        .degraded-list { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 7px; }
        .degraded-list code { font-size: 10px; }
        .sources { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--divider-color); font-size: 11px; opacity: .72; }
        .sources code { background: var(--secondary-background-color); border-radius: 4px; padding: 2px 5px; }
        .footer { margin-top: 10px; font-size: 11px; opacity: .5; }
        .error { padding: 16px; color: var(--error-color); }
      </style>
      <ha-card>
        <div class="top" id="top">
          <div class="title">${this._escape(this._config.title)}</div>
          <div class="level-row">
            <div class="level">DEFCON ${this._escape(level)}</div>
            <div class="name">${this._escape(attrs.level_name || "Normal")}</div>
          </div>
          <div class="summary">${this._escape(attrs.summary || labels.noReasons)}</div>
          <div class="meta">
            <span class="pill">${labels.external}: DEFCON ${this._escape(externalLevel)}</span>
            <span class="pill">${labels.infrastructure}: DEFCON ${this._escape(infrastructureLevel)}</span>
            <span class="pill">${labels.automatic}: DEFCON ${this._escape(autoLevel)}</span>
            ${contextHtml}
            ${manual !== "auto" ? `<span class="pill">${labels.manual}: ${this._escape(manual.replace("defcon_", "DEFCON "))}</span>` : ""}
          </div>
        </div>
        <div class="body">
          <div class="section-title">${labels.reasons}</div>
          ${reasonsHtml}
          ${degradedHtml}
          ${sourceHtml}
          ${evaluated ? `<div class="footer">${labels.updated}: ${this._escape(evaluated)}</div>` : ""}
        </div>
      </ha-card>`;

    this.shadowRoot.getElementById("top")?.addEventListener("click", () => {
      this.dispatchEvent(
        new CustomEvent("hass-more-info", {
          bubbles: true,
          composed: true,
          detail: { entityId: this._config.entity },
        })
      );
    });

    this.shadowRoot.getElementById("context-pill")?.addEventListener("click", (event) => {
      event.stopPropagation();
      this.dispatchEvent(
        new CustomEvent("hass-more-info", {
          bubbles: true,
          composed: true,
          detail: { entityId: this._config.context_entity },
        })
      );
    });
  }
}

if (!customElements.get("defcon-ha-card")) {
  customElements.define("defcon-ha-card", DefconHaCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "defcon-ha-card")) {
  window.customCards.push({
    type: "defcon-ha-card",
    name: "DEFCON Home",
    description: "Local deterministic household situation engine with advisory context.",
    preview: true,
    getEntitySuggestion: (hass, entityId) => {
      const state = hass.states?.[entityId];
      return state?.attributes?.engine === "local_deterministic"
        ? {
            entity: entityId,
            context_entity: "sensor.defcon_home_context_recommended_defcon",
          }
        : null;
    },
  });
}
