export function StyleGuidePage() {
  return (
    <section className="style-guide-page">
      <h1>Style Guide</h1>
      <p>Living visual reference for cards, chips, portrait headers, and timeline patterns.</p>

      <div className="panel">
        <h2>Typography</h2>
        <h3>Section Heading</h3>
        <p>
          Body copy should stay compact, readable, and information-forward. Secondary text uses muted color.
        </p>
      </div>

      <div className="member-hero-card">
        <img
          className="member-portrait"
          src="https://ui-avatars.com/api/?name=Sample+Member&background=1e5fa8&color=ffffff&size=256"
          alt="Sample portrait"
        />
        <div className="member-hero-content">
          <h2>Portrait Card Pattern</h2>
          <p className="member-subtitle">Used for member profile headers and person-centric detail pages.</p>
          <div className="member-chips">
            <span className="chip">Party: Independent</span>
            <span className="chip">State: CA</span>
            <span className="chip">Current term: 119th</span>
          </div>
        </div>
      </div>

      <div className="timeline-lane">
        <h2>Vertical Timeline Pattern</h2>
        <ul className="vertical-timeline">
          <li className="timeline-item">
            <article className="timeline-card">
              <div className="timeline-card-top">
                <span className="party-dot party-dot-democrat" aria-hidden="true" />
                <span className="chip">Congress 119</span>
              </div>
              <h3>Sample Event Card</h3>
              <p>Use this layout for state/member history and bill actions.</p>
            </article>
          </li>
          <li className="timeline-item">
            <article className="timeline-card">
              <div className="timeline-card-top">
                <span className="party-dot party-dot-republican" aria-hidden="true" />
                <span className="chip">Congress 118</span>
              </div>
              <h3>Secondary Event</h3>
              <p>Keep titles short and place detail metadata in supporting text.</p>
            </article>
          </li>
        </ul>
      </div>

      <div className="panel">
        <h2>Chip + Badge Rhythm</h2>
        <div className="chip-row">
          <span className="chip">Draft</span>
          <span className="chip">Scaffold</span>
          <span className="chip">Backend Contracted</span>
          <button className="chip-button chip-button-active" type="button">
            Active Filter
          </button>
        </div>
      </div>
    </section>
  );
}
