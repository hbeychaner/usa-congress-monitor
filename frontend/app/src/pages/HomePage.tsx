import { Link } from 'react-router-dom';

export function HomePage() {
  return (
    <section className="home-page">
      <h1>Congress Tracker</h1>
      <p>Search the congressional record, browse states, and inspect members.</p>

      <div className="card-grid">
        <Link className="card" to="/states">
          <h2>Map View</h2>
          <p>Browse states and view their current congressional delegation.</p>
        </Link>
        <Link className="card" to="/bills">
          <h2>Bill Activity</h2>
          <p>Browse recently updated bills from OpenSearch.</p>
        </Link>
        <Link className="card" to="/topics">
          <h2>Topic Explorer</h2>
          <p>Explore indexed topic associations.</p>
        </Link>
        <Link className="card" to="/search">
          <h2>Global Search</h2>
          <p>Run typed member/state/bill queries with backend relevance scoring.</p>
        </Link>
      </div>
    </section>
  );
}
