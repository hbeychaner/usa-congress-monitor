import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { fetchStateTimeline, type StateTimelineResponse, type TimelineMember } from '../api/states';

function partyClass(party: string): string {
  const normalized = party.toLowerCase();
  return normalized === 'democratic' ? 'democrat' : normalized;
}

function ChamberSection({ title, members }: { title: string; members: TimelineMember[] }) {
  return (
    <section className="chamber-section">
      <h2>{title}</h2>
      {members.length === 0 ? (
        <p>No members in selected range.</p>
      ) : (
        <ul className="timeline-group-members">
          {members.map((member) => (
            <li key={`${member.bioguide_id}-${member.congress_start}`} className="timeline-item">
              <article className="timeline-card">
                <div className="timeline-card-top"><span className={`party-dot party-dot-${partyClass(member.party)}`} aria-hidden="true" /><span className="chip">{member.congress_start}-{member.congress_end}</span></div>
                <h3><Link to={`/members/${member.bioguide_id}`}>{member.name}</Link></h3>
                <p>{member.party} · Bioguide {member.bioguide_id}</p>
              </article>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function StateDetailPage() {
  const { stateCode = '' } = useParams();
  const [timeline, setTimeline] = useState<StateTimelineResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fromCongress, setFromCongress] = useState<number>(116);
  const [toCongress, setToCongress] = useState<number>(119);

  useEffect(() => {
    setLoading(true);
    fetchStateTimeline(stateCode, { fromCongress, toCongress })
      .then((data) => setTimeline(data))
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, [stateCode, fromCongress, toCongress]);

  if (loading) {
    return <p>Loading timeline...</p>;
  }

  if (error || !timeline) {
    return <p>Failed to load timeline: {error ?? 'Unknown error'}</p>;
  }

  const houseGroups = timeline.house.groups ?? [];
  const senateGroups = timeline.senate.groups ?? [];
  const congresses = [...new Set([
    ...houseGroups.map((group) => group.congress),
    ...senateGroups.map((group) => group.congress),
  ])].sort((left, right) => right - left);
  const houseByCongress = new Map(houseGroups.map((group) => [group.congress, group.members]));
  const senateByCongress = new Map(senateGroups.map((group) => [group.congress, group.members]));

  return (
    <section className="state-detail-page">
      <h1>
        {timeline.state_name} ({timeline.state_code})
      </h1>
      <p>Delegations grouped by Congress from OpenSearch member records.</p>

      <div className="timeline-controls panel">
        <h2>Timeline Filters</h2>
        <div className="filter-grid">
          <label>
            From Congress
            <input
              className="search-input"
              type="number"
              value={fromCongress}
              min={1}
              onChange={(event) => setFromCongress(Number(event.target.value || 1))}
            />
          </label>
          <label>
            To Congress
            <input
              className="search-input"
              type="number"
              value={toCongress}
              min={1}
              onChange={(event) => setToCongress(Number(event.target.value || 1))}
            />
          </label>
        </div>
      </div>

      <div className="timeline-stats">
        <div className="panel">
          <h2>House Seats</h2>
          <p>{timeline.house.members.length} matching timeline entries</p>
        </div>
        <div className="panel">
          <h2>Senate Seats</h2>
          <p>{timeline.senate.members.length} matching timeline entries</p>
        </div>
      </div>

      <div className="timeline-grid congress-grid">
        {congresses.map((congress) => (
          <section className="timeline-lane congress-column" key={congress}>
            <h2>Congress {congress}</h2>
            <ChamberSection title="House" members={houseByCongress.get(congress) ?? []} />
            <ChamberSection title="Senate" members={senateByCongress.get(congress) ?? []} />
          </section>
        ))}
      </div>
    </section>
  );
}
