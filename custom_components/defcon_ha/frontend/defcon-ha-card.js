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
    this._config = { title: "DEFCON Home", show_sources: true, ...config };
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
    return Math.max(3, Math.min(8, 3 + count));
  }

  static getStubConfig(hass) {
    const entity = Object.keys(hass?.states || {}).find(
      (id) => id.startsWith("sensor.") && hass.states[id]?.attributes?.automatic_level !== undefined
    );
    return { entity: entity || "sensor.defcon_home_level" };
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
        normal: "Normal",
        automatic: "Automatic",
        manual: "Manual override",
        reasons: "Why",
        noReasons: "No active warning or monitored disruption",
        sources: "Sources",
        updated: "Evaluated",
      },
      fr: {
        normal: "Normal",
        automatic: "Automatique",
        manual: "Override manuel",
        reasons: "Pourquoi",
        noReasons: "Aucune alerte ou perturbation surveill\u00e9e active",
        sources: "Sources",
        updated: "\u00c9valu\u00e9",
      },
      de: {
        normal: "Normal",
        automatic: "Automatisch",
        manual: "Manueller Override",
        reasons: "Warum",
        noReasons: "Keine aktive Warnung oder \u00fcberwachte St\u00f6rung",
        sources: "Quellen",
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
      .replaceAll('\"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  _sourceIcon(source) {
    switch ((source || "").toUpperCase()) {
      case "NINA": return "\u26a0";
      case "DWD": return "\u2601";
      case "HVV": return "\u2194";
      default: return "\u2022";
    }
  }

  _render() {
    if (!this.shadowRoot || !this._config?.entity || !this._hass) return;

    const stateObj = this._hass.states[this._config.entity];
    const labels = this._labels();
    if (!stateObj) {
      this.shadowRoot.innerHTML = `<ha-card><div class="error">Entity ${this._escape(this._config.entity)} not found</div></ha-card>`;
      return;
    }

    const attrs = stateObj.attributes || {};
    const level = Number(stateObj.state) || 5;
    const autoLevel = Number(attrs.automatic_level) || level;
    const localLevel = Number(attrs.local_level) || 5;
    const contextLevel = attrs.context_level == null ? null : Number(attrs.context_level);
    const contextStatus = attrs.context_status || "unknown";
    const color = attrs.color || "var(--primary-color)";
    const reasons = Array.isArray(attrs.reasons) ? attrs.reasons : [];
    const sourceEntities = Array.isArray(attrs.source_entities) ? attrs.source_entities : [];
    const manual = attrs.manual_override || "auto";
    const report = attrs.context_report || "";
    const evaluated = attrs.evaluated_at
      ? new Date(attrs.evaluated_at).toLocaleString(this._hass.language)
      : "";

    const reasonsHtml = reasons.length
      ? reasons.map((reason) => `
          <div class="reason">
            <div class="reason-head">
              <span class="source">${this._escape(this._sourceIcon(reason.source))} ${this._escape(reason.source)}</span>
              <span class="reason-level">DEFCON ${this._escape(reason.level)}</span>
            </div>
            <div class="reason-title">${this._escape(reason.title)}</div>
            ${reason.detail ? `<div class="reason-detail">${this._escape(reason.detail)}</div>` : ""}
          </div>`).join("")
      : `<div class="empty">${labels.noReasons}</div>`;

    const sourceHtml = this._config.show_sources !== false && sourceEntities.length
      ? `<div class="sources"><span>${labels.sources}</span>${sourceEntities.map((id) => `<code>${this._escape(id)}</code>`).join("")}</div>`
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
        .body { padding: 14px 16px 16px; }
        .context-box { background: var(--secondary-background-color); border-radius: 10px; padding: 10px; margin-bottom: 12px; font-size: 13px; line-height: 1.35; }
        .context-meta { margin-top: 5px; font-size: 11px; opacity: .62; }
        .report { white-space: pre-wrap; font-size: 13px; line-height: 1.45; background: var(--secondary-background-color); border-radius: 10px; padding: 12px; margin: 10px 0 14px; }
        .section-title { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; opacity: .65; margin-bottom: 8px; }
        .reason { padding: 10px 0; border-top: 1px solid var(--divider-color); }
        .reason:first-of-type { border-top: 0; }
        .reason-head { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
        .source { font-size: 12px; font-weight: 700; opacity: .7; }
        .reason-level { font-size: 11px; font-weight: 700; border-radius: 999px; padding: 3px 7px; background: var(--secondary-background-color); }
        .reason-title { margin-top: 4px; font-weight: 650; line-height: 1.25; }
        .reason-detail { margin-top: 4px; font-size: 13px; line-height: 1.35; opacity: .78; }
        .empty { font-size: 14px; opacity: .72; padding: 4px 0 8px; }
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
            <div class="name">${this._escape(attrs.level_name || labels.normal)}</div>
          </div>
          <div class="summary">${this._escape(attrs.summary || labels.noReasons)}</div>
          <div class="meta">
            <span class="pill">Local: DEFCON ${this._escape(localLevel)}</span>
            <span class="pill">Context: ${contextLevel == null ? "—" : "DEFCON " + this._escape(contextLevel)} (${this._escape(contextStatus)})</span>
            <span class="pill">${labels.automatic}: DEFCON ${this._escape(autoLevel)}</span>
            ${manual !== "auto" ? `<span class="pill">${labels.manual}: ${this._escape(manual.replace("defcon_", "DEFCON "))}</span>` : ""}
          </div>
        </div>
        <div class="body">
          <div class="section-title">Context</div>
          <div class="context-box">${this._escape(attrs.context_summary || "No context feed available")}<div class="context-meta">Status: ${this._escape(contextStatus)} · valid until: ${this._escape(attrs.context_valid_until || "—")}</div></div>
          ${report ? `<div class="section-title">Rapport contextuel</div><div class="report">${this._escape(report)}</div>` : ""}
          <div class="section-title">${labels.reasons}</div>
          ${reasonsHtml}
          ${sourceHtml}
          ${evaluated ? `<div class="footer">${labels.updated}: ${this._escape(evaluated)}</div>` : ""}
        </div>
      </ha-card>`;

    this.shadowRoot.getElementById("top")?.addEventListener("click", () => {
      this.dispatchEvent(new CustomEvent("hass-more-info", {
        bubbles: true,
        composed: true,
        detail: { entityId: this._config.entity },
      }));
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
    description: "Household situation level with active reasons from NINA, DWD, HVV and other HA entities.",
    preview: true,
    getEntitySuggestion: (hass, entityId) => {
      const state = hass.states?.[entityId];
      return state?.attributes?.automatic_level !== undefined ? { entity: entityId } : null;
    },
  });
}
