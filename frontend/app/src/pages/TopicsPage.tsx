import { Link } from 'react-router-dom';

const SAMPLE_TOPICS = [
  {
    label: 'Energy Transition',
    memberCount: 72,
    avgConfidence: 0.78,
  },
  {
    label: 'Infrastructure',
    memberCount: 65,
    avgConfidence: 0.71,
  },
  {
    label: 'Healthcare Access',
    memberCount: 59,
    avgConfidence: 0.67,
  },
];

export function TopicsPage() {
  return (
    <section className="topics-page">
      <h1>Topics</h1>
      <p>
        Topic profiles are scaffolded for now and will be populated from backend NLP pipelines as ingest completes.
      </p>

      <div className="card-grid">
        {SAMPLE_TOPICS.map((topic) => (
          <article key={topic.label} className="card">
            <h2>
              <Link to={`/topics/${topic.label.toLowerCase().replace(/\s+/g, '-')}`}>{topic.label}</Link>
            </h2>
            <p>Members tagged: {topic.memberCount}</p>
            <p>Average confidence: {Math.round(topic.avgConfidence * 100)}%</p>
            <div className="topic-bar">
              <div className="topic-bar-fill" style={{ width: `${Math.round(topic.avgConfidence * 100)}%` }} />
            </div>
          </article>
        ))}
      </div>

      <div className="panel">
        <h2>Planned Backend Contract</h2>
        <p>
          The final UI will consume <strong>GET /api/v1/members/{'{id}'}/topics</strong> plus aggregate topic endpoints.
        </p>
        <p>
          For now, explore an archived <Link to="/members/H001092">member profile</Link>.
        </p>
      </div>
    </section>
  );
}
