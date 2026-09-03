import { useParams } from 'react-router-dom';

export function TopicDetailPage() {
  const { topicLabel = 'topic' } = useParams();
  const title = topicLabel.replace(/-/g, ' ');

  return (
    <section className="topic-detail-page">
      <h1>{title}</h1>
      <p>Topic detail scaffold page for explaining member-topic associations and provenance.</p>

      <div className="panel">
        <h2>Topic Notes</h2>
        <p>
          Placeholder: backend NLP pipeline will return representative phrases and bill references for this topic.
        </p>
      </div>

      <div className="panel">
        <h2>Related Members</h2>
        <p>No indexed member associations are available for this topic.</p>
      </div>
    </section>
  );
}
