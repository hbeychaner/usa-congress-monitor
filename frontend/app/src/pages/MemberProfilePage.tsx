import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { fetchMemberProfile, type MemberProfileResponse } from '../api/members';

const PARTY_BADGES: Record<string, string> = {
  Democratic: 'https://img.shields.io/badge/D-Democratic-1e5fa8?style=flat-square',
  Republican: 'https://img.shields.io/badge/R-Republican-b33a3a?style=flat-square',
};

export function MemberProfilePage() {
  const { bioguideId = '' } = useParams();
  const [profile, setProfile] = useState<MemberProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [portraitFailed, setPortraitFailed] = useState(false);

  useEffect(() => {
    fetchMemberProfile(bioguideId)
      .then((data) => setProfile(data))
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, [bioguideId]);

  if (loading) {
    return <p>Loading member profile...</p>;
  }

  if (error || !profile) {
    return <p>Failed to load member profile: {error ?? 'Unknown error'}</p>;
  }

  const activityByType = profile.recent_activity.reduce<Record<string, number>>((acc, item) => {
    acc[item.activity_type] = (acc[item.activity_type] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <section className="member-page">
      <div className="member-hero-card">
        {profile.member.image_url && !portraitFailed ? (
          <img
            className="member-portrait"
            src={profile.member.image_url}
            alt={`${profile.member.display_name} portrait`}
            onError={() => setPortraitFailed(true)}
          />
        ) : null}
        <div className="member-hero-content">
          <h1>{profile.member.display_name}</h1>
          <p className="member-subtitle">
            {profile.member.chamber ?? 'Chamber unavailable'} · {profile.member.state}
          </p>
          <div className="member-chips">
            {PARTY_BADGES[profile.member.party] ? (
              <img
                className="party-badge"
                src={PARTY_BADGES[profile.member.party]}
                alt={`${profile.member.party} Party`}
              />
            ) : <span className="chip">{profile.member.party}</span>}
            {profile.member.district != null ? <span className="chip">District: {profile.member.district}</span> : null}
            {profile.member.term_start_year != null ? (
              <span className="term-timeline" aria-label={`Term from ${profile.member.term_start_year}${profile.member.term_end_year ? ` to ${profile.member.term_end_year}` : ''}`}>
                <span className="term-timeline-year">{profile.member.term_start_year}</span>
                <span className="term-timeline-track" aria-hidden="true" />
                <span className="term-timeline-year">{profile.member.term_end_year ?? 'present'}</span>
              </span>
            ) : null}
            <span className="chip">Bioguide: {profile.member.bioguide_id}</span>
          </div>
        </div>
      </div>

      <div className="panel">
        <h2>Activity Breakdown</h2>
        <div className="chip-row">
          {Object.entries(activityByType).map(([activityType, count]) => (
            <span key={activityType} className="chip">
              {activityType}: {count}
            </span>
          ))}
        </div>
      </div>

      <div className="panel">
        <h2>Recent Activity</h2>
        {profile.recent_activity.length > 0 ? (
          <ul>
            {profile.recent_activity.map((item) => (
              <li key={`${item.bill_id}:${item.activity_type}`}>
                <strong>{item.activity_type}</strong>: {item.title} (
                <Link to={`/bills/${encodeURIComponent(item.bill_id)}`}>{item.bill_id}</Link>)
              </li>
            ))}
          </ul>
        ) : <p>No indexed bill activity for this member.</p>}
      </div>

      <div className="panel">
        <h2>Topic Profile</h2>
        {profile.topics.length > 0 ? <ul className="topic-list">
          {profile.topics.map((topic) => (
            <li key={topic.label}>
              <div className="topic-row">
                <span>{topic.label}</span>
                <strong>{Math.round(topic.weight * 100)}%</strong>
              </div>
              <div className="topic-bar">
                <div className="topic-bar-fill" style={{ width: `${Math.round(topic.weight * 100)}%` }} />
              </div>
            </li>
          ))}
        </ul> : <p>No indexed topic associations for this member.</p>}
      </div>
    </section>
  );
}
