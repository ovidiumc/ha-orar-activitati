/**
 * Orar & Activitati - Lovelace card.
 *
 * Draws one column per child: what is on right now, what is left today and,
 * underneath, a shared strip with tomorrow's first items.
 *
 * The card finds its entities through the `vizualizare` attribute rather
 * than through entity ids, so renaming an entity or switching Home
 * Assistant's language cannot break it.
 */

const CARD_VERSION = "1.4.0";

/** Sensors carrying a child's timetable, keyed by their `vizualizare`. */
const VIEWS = ["acum", "urmatoarea", "azi", "maine"];

/** Fallback accent, used when a child has no colour configured. */
const FALLBACK_COLOR = "#2196f3";

const ICONS = {
  scoala: "mdi:school",
  activitate: "mdi:star-four-points",
  pauza: "mdi:food-apple",
};

/** Escape a value before it goes into the template literals below. */
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[char],
  );

/**
 * Group this integration's sensors by child.
 *
 * Returns a Map of child name to { acum, urmatoarea, azi, maine, culoare,
 * clasa }, so a child whose entities are still loading simply comes back
 * with fewer keys rather than breaking the render.
 */
function collectChildren(hass) {
  const children = new Map();

  for (const state of Object.values(hass.states)) {
    const attrs = state.attributes || {};
    const view = attrs.vizualizare;
    const child = attrs.copil;

    if (!VIEWS.includes(view) || !child) continue;

    if (!children.has(child)) {
      children.set(child, { nume: child, clasa: null, culoare: null });
    }

    const bucket = children.get(child);
    bucket[view] = state;
    bucket.clasa = bucket.clasa ?? attrs.clasa ?? null;
    bucket.culoare = bucket.culoare ?? attrs.culoare ?? null;
  }

  return children;
}

/** Render one slot row: time on top, icon + title underneath. */
function renderSlot(slot, { highlight = false } = {}) {
  if (!slot) return "";

  const icon = slot.iconita || ICONS[slot.tip] || ICONS.scoala;
  const room = slot.sala ? ` (${esc(slot.sala)})` : "";

  // The location link is rendered as a plain anchor rather than a click
  // handler so it still works when the card is used inside a dashboard
  // that swallows events (a swipe card, a popup).
  const link = slot.locatie_url
    ? `<a class="link" href="${esc(slot.locatie_url)}" target="_blank" rel="noopener noreferrer">
         <ha-icon icon="mdi:map-marker"></ha-icon>
       </a>`
    : "";

  const online = slot.online
    ? `<ha-icon class="online" icon="mdi:laptop" title="Online"></ha-icon>`
    : "";

  return `
    <div class="slot ${highlight ? "is-now" : ""}">
      <ha-icon class="kind" icon="${esc(icon)}"></ha-icon>
      <div class="body">
        <div class="time">${esc(slot.interval || "")}</div>
        <div class="title">${online}${esc(slot.titlu || "")}${room}</div>
      </div>
      ${link}
    </div>
  `;
}

/**
 * Return today's slots that have not started yet.
 *
 * Derived from the `azi` sensor and the current slot rather than from the
 * clock: the sensors already recompute at every boundary, so this stays in
 * step with them without the card needing its own timer.
 */
function upcomingToday(child) {
  const all = child.azi?.attributes?.activitati || [];
  const now = child.acum?.attributes;

  if (!now || now.liber) {
    // Nothing running: everything whose start is still ahead. Comparing the
    // HH:MM strings is safe -- they are zero-padded and same-length.
    const nextStart = child.urmatoarea?.attributes?.ora_inceput;
    const sameDay =
      child.urmatoarea?.attributes?.data === child.azi?.attributes?.data;
    if (!nextStart || !sameDay) return [];
    return all.filter((slot) => slot.ora_inceput >= nextStart);
  }

  return all.filter((slot) => slot.ora_inceput >= now.ora_sfarsit);
}

class OrarActivitatiCard extends HTMLElement {
  static getStubConfig() {
    return { title: "Organizare activități și școală" };
  }

  setConfig(config) {
    this._config = {
      title: "Organizare activități și școală",
      // Names, in the order the columns should appear. Left empty, every
      // configured child is shown, alphabetically.
      copii: [],
      // How many of tomorrow's items the footer strip lists per child.
      maine_maxim: 2,
      arata_maine: true,
      ...(config || {}),
    };
    this._rendered = null;
  }

  getCardSize() {
    return 6;
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _children() {
    const found = collectChildren(this._hass);
    const wanted = this._config.copii;

    if (wanted && wanted.length) {
      return wanted.map((name) => found.get(name)).filter(Boolean);
    }

    return [...found.values()].sort((a, b) =>
      a.nume.localeCompare(b.nume, "ro"),
    );
  }

  _render() {
    if (!this._hass || !this._config) return;

    const children = this._children();
    const html = this._html(children);

    // Re-rendering only on change keeps the anchors clickable and stops the
    // card flickering on every state update of an unrelated entity.
    if (html === this._rendered) return;
    this._rendered = html;

    if (!this._card) {
      this._card = document.createElement("ha-card");
      this._style = document.createElement("style");
      this._style.textContent = STYLES;
      this.innerHTML = "";
      this.appendChild(this._style);
      this.appendChild(this._card);
    }

    this._card.innerHTML = html;
  }

  _html(children) {
    if (!children.length) {
      return `
        <div class="empty">
          Niciun copil configurat încă.<br />
          Adaugă unul din <b>Setări → Dispozitive și servicii → Orar &amp; Activități</b>.
        </div>
      `;
    }

    return `
      <h1 class="card-title">${esc(this._config.title)}</h1>
      <div class="grid" style="--columns: ${children.length}">
        ${children.map((child) => this._column(child)).join("")}
      </div>
      ${this._config.arata_maine ? this._tomorrow(children) : ""}
    `;
  }

  _column(child) {
    const color = child.culoare || FALLBACK_COLOR;
    const now = child.acum?.attributes;
    const today = child.azi?.attributes;
    const upcoming = upcomingToday(child);

    const nowBlock =
      now && !now.liber
        ? renderSlot(now, { highlight: true })
        : `<div class="slot is-now free">
             <ha-icon class="kind" icon="mdi:coffee"></ha-icon>
             <div class="body"><div class="title">Liber acum</div></div>
           </div>`;

    const upcomingBlock = upcoming.length
      ? upcoming.map((slot) => renderSlot(slot)).join("")
      : `<div class="note">Nimic altceva azi</div>`;

    // A free day is not an empty day: the lessons are gone but the
    // activities are not, so the banner says why school is off rather than
    // replacing the column.
    const freeDay = today?.zi_libera
      ? `<div class="freeday">
           <ha-icon icon="mdi:party-popper"></ha-icon>
           <span>Zi liberă${
             today.denumire_zi_libera
               ? ` — ${esc(today.denumire_zi_libera)}`
               : ""
           }</span>
         </div>`
      : "";

    return `
      <section class="child" style="--accent: ${esc(color)}">
        <header class="child-head">
          <ha-icon icon="mdi:account-child"></ha-icon>
          <span>${esc(child.nume)}</span>
          ${child.clasa ? `<small>(${esc(child.clasa)})</small>` : ""}
        </header>
        <div class="child-body">
          ${freeDay}
          <div class="section-label">
            Acum${today?.zi ? ` (${esc(today.zi)})` : ""}
          </div>
          ${nowBlock}
          <div class="section-label">Urmează azi</div>
          <div class="upcoming">${upcomingBlock}</div>
        </div>
      </section>
    `;
  }

  _tomorrow(children) {
    const limit = Number(this._config.maine_maxim) || 2;

    // Each child's lookahead is their own next day with something on it, so
    // two children can be looking at different days -- one with a Saturday
    // practice, one whose next thing is Monday's first lesson.
    const blocks = children
      .map((child) => ({ child, attrs: child.maine?.attributes }))
      .filter(({ attrs }) => attrs && (attrs.activitati || []).length);

    if (!blocks.length) return "";

    const days = new Set(blocks.map(({ attrs }) => attrs.data));
    const sameDay = days.size === 1;

    // Flattened and sorted by when it actually happens, not grouped by
    // child: with two children looking at different days, grouping put
    // Tuesday above Monday, which reads as the wrong week.
    const items = blocks
      .flatMap(({ child, attrs }) =>
        (attrs.activitati || [])
          .slice(0, limit)
          .map((slot) => ({ child, attrs, slot })),
      )
      .sort(
        (a, b) =>
          // The ISO date and the zero-padded HH:MM both sort as plain text.
          a.attrs.data.localeCompare(b.attrs.data) ||
          a.slot.ora_inceput.localeCompare(b.slot.ora_inceput) ||
          a.child.nume.localeCompare(b.child.nume, "ro"),
      );

    const lines = items.map(
      ({ child, attrs, slot }) => `
        <div class="tomorrow-line">
          ${sameDay ? "" : `<span class="tomorrow-day">${esc(attrs.zi)}</span>`}
          <span class="tomorrow-time">${esc(slot.interval)}</span>
          <span class="tomorrow-sep">|</span>
          <span class="tomorrow-who">${esc(child.nume)}:</span>
          <span>${esc(slot.titlu)}</span>
        </div>
      `,
    );

    return `
      <div class="tomorrow">
        <div class="tomorrow-head">
          <ha-icon icon="mdi:calendar"></ha-icon>
          <span>${esc(this._lookaheadHeading(blocks, sameDay))}</span>
        </div>
        ${lines.join("")}
      </div>
    `;
  }

  /**
   * Label the lookahead band.
   *
   * "Mâine" is only honest when the day really is tomorrow. Friday evening
   * looks ahead to Monday, so the band names the day instead; when the
   * children are looking at different days it drops to a generic heading
   * and each line carries its own day.
   */
  _lookaheadHeading(blocks, sameDay) {
    if (!sameDay) return "Urmează";

    const { attrs } = blocks[0];
    let when = `${attrs.zi}, ${formatDate(attrs.data)}`;
    if (attrs.zi_libera && attrs.denumire_zi_libera) {
      when += ` · ${attrs.denumire_zi_libera}`;
    }

    return attrs.este_maine ? `Mâine (${when})` : when;
  }
}

/** Render an ISO date as e.g. "26 sep". */
function formatDate(iso) {
  if (!iso) return "";
  const parsed = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return iso;
  return parsed
    .toLocaleDateString("ro-RO", { day: "numeric", month: "short" })
    .replace(".", "");
}

const STYLES = `
  orar-activitati-card ha-card {
    padding: 16px;
    background: var(--card-background-color);
  }
  orar-activitati-card .card-title {
    margin: 0 0 16px;
    font-size: 1.35rem;
    font-weight: 800;
    letter-spacing: 0.04em;
    text-align: center;
    text-transform: uppercase;
    color: var(--primary-text-color);
  }
  orar-activitati-card .grid {
    display: grid;
    grid-template-columns: repeat(var(--columns, 2), minmax(0, 1fr));
    gap: 12px;
  }
  /* One column per child is unreadable on a phone, so they stack instead. */
  @media (max-width: 600px) {
    orar-activitati-card .grid { grid-template-columns: 1fr; }
  }
  orar-activitati-card .child {
    border: 2px solid var(--accent);
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 0 10px -2px var(--accent);
  }
  orar-activitati-card .child-head {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 8px;
    background: var(--accent);
    color: #fff;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }
  orar-activitati-card .child-head small { font-weight: 600; opacity: 0.9; }
  orar-activitati-card .child-body { padding: 10px; }
  orar-activitati-card .section-label {
    margin: 6px 2px 4px;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--secondary-text-color);
  }
  orar-activitati-card .freeday {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 6px 0 2px;
    padding: 6px 10px;
    border-radius: 10px;
    background: color-mix(in srgb, var(--accent) 18%, transparent);
    border: 1px dashed var(--accent);
    color: var(--primary-text-color);
    font-weight: 700;
  }
  orar-activitati-card .freeday ha-icon { color: var(--accent); }
  orar-activitati-card .slot {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border-radius: 10px;
    background: var(--secondary-background-color);
  }
  orar-activitati-card .upcoming .slot { margin-bottom: 6px; }
  orar-activitati-card .upcoming .slot:last-child { margin-bottom: 0; }
  orar-activitati-card .slot.is-now {
    border: 2px solid var(--accent);
    background: color-mix(in srgb, var(--accent) 12%, transparent);
  }
  orar-activitati-card .slot.free { opacity: 0.75; }
  orar-activitati-card .slot .kind { color: var(--accent); flex: 0 0 auto; }
  orar-activitati-card .slot .body { flex: 1 1 auto; min-width: 0; }
  orar-activitati-card .slot .time {
    font-weight: 700;
    color: var(--primary-text-color);
  }
  orar-activitati-card .slot .title {
    color: var(--primary-text-color);
    overflow-wrap: anywhere;
  }
  orar-activitati-card .slot .online {
    --mdc-icon-size: 18px;
    margin-right: 4px;
    color: var(--accent);
    vertical-align: -4px;
  }
  orar-activitati-card .slot .link { color: var(--accent); flex: 0 0 auto; }
  orar-activitati-card .note {
    padding: 8px 10px;
    color: var(--secondary-text-color);
    font-style: italic;
  }
  orar-activitati-card .tomorrow {
    margin-top: 12px;
    padding: 10px 14px;
    border-radius: 12px;
    background: var(--secondary-background-color);
  }
  orar-activitati-card .tomorrow-head {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 6px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--primary-text-color);
  }
  orar-activitati-card .tomorrow-line {
    color: var(--primary-text-color);
    line-height: 1.6;
  }
  orar-activitati-card .tomorrow-day {
    display: inline-block;
    min-width: 5.5em;
    font-weight: 700;
    color: var(--secondary-text-color);
  }
  orar-activitati-card .tomorrow-time { font-variant-numeric: tabular-nums; }
  orar-activitati-card .tomorrow-sep { opacity: 0.4; margin: 0 6px; }
  orar-activitati-card .tomorrow-who { font-weight: 700; }
  orar-activitati-card .empty {
    padding: 24px;
    text-align: center;
    color: var(--secondary-text-color);
    line-height: 1.7;
  }
`;

if (!customElements.get("orar-activitati-card")) {
  customElements.define("orar-activitati-card", OrarActivitatiCard);

  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "orar-activitati-card",
    name: "Orar & Activități",
    description:
      "Orarul și activitățile copiilor: ce e acum, ce urmează azi și ce e mâine.",
    preview: true,
  });

  console.info(
    `%c ORAR-ACTIVITATI-CARD %c ${CARD_VERSION} `,
    "color: white; background: #2196f3; font-weight: 700;",
    "color: #2196f3; background: white; font-weight: 700;",
  );
}
