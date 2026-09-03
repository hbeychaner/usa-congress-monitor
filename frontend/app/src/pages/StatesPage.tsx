import { useEffect, useState } from 'react';
import { ComposableMap, Geographies, Geography } from 'react-simple-maps';
import { useNavigate } from 'react-router-dom';
import { fetchStateTimeline, type StateTimelineResponse } from '../api/states';

const US_STATES_TOPO_JSON = 'https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json';

const FIPS_TO_STATE_CODE: Record<string, string> = {
  '01': 'AL', '02': 'AK', '04': 'AZ', '05': 'AR', '06': 'CA', '08': 'CO', '09': 'CT',
  '10': 'DE', '11': 'DC', '12': 'FL', '13': 'GA', '15': 'HI', '16': 'ID', '17': 'IL',
  '18': 'IN', '19': 'IA', '20': 'KS', '21': 'KY', '22': 'LA', '23': 'ME', '24': 'MD',
  '25': 'MA', '26': 'MI', '27': 'MN', '28': 'MS', '29': 'MO', '30': 'MT', '31': 'NE',
  '32': 'NV', '33': 'NH', '34': 'NJ', '35': 'NM', '36': 'NY', '37': 'NC', '38': 'ND',
  '39': 'OH', '40': 'OK', '41': 'OR', '42': 'PA', '44': 'RI', '45': 'SC', '46': 'SD',
  '47': 'TN', '48': 'TX', '49': 'UT', '50': 'VT', '51': 'VA', '53': 'WA', '54': 'WV',
  '55': 'WI', '56': 'WY',
};

const STATE_NAMES: Record<string, string> = {
  AL: 'Alabama', AK: 'Alaska', AZ: 'Arizona', AR: 'Arkansas', CA: 'California', CO: 'Colorado',
  CT: 'Connecticut', DE: 'Delaware', FL: 'Florida', GA: 'Georgia', HI: 'Hawaii', ID: 'Idaho',
  IL: 'Illinois', IN: 'Indiana', IA: 'Iowa', KS: 'Kansas', KY: 'Kentucky', LA: 'Louisiana',
  ME: 'Maine', MD: 'Maryland', MA: 'Massachusetts', MI: 'Michigan', MN: 'Minnesota', MS: 'Mississippi',
  MO: 'Missouri', MT: 'Montana', NE: 'Nebraska', NV: 'Nevada', NH: 'New Hampshire', NJ: 'New Jersey',
  NM: 'New Mexico', NY: 'New York', NC: 'North Carolina', ND: 'North Dakota', OH: 'Ohio', OK: 'Oklahoma',
  OR: 'Oregon', PA: 'Pennsylvania', RI: 'Rhode Island', SC: 'South Carolina', SD: 'South Dakota',
  TN: 'Tennessee', TX: 'Texas', UT: 'Utah', VT: 'Vermont', VA: 'Virginia', WA: 'Washington',
  WV: 'West Virginia', WI: 'Wisconsin', WY: 'Wyoming', DC: 'District of Columbia',
};

export function StatesPage() {
  const navigate = useNavigate();
  const [selectedCode, setSelectedCode] = useState('');
  const [timeline, setTimeline] = useState<StateTimelineResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedCode) return;
    setLoading(true);
    setError(null);
    fetchStateTimeline(selectedCode, { fromCongress: 119, toCongress: 119 })
      .then(setTimeline)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [selectedCode]);

  return (
    <section className="states-map-page">
      <h1>States</h1>
      <p>Select a state to preview its 119th Congress delegation. Open the state for its full history.</p>

      <div className="map-layout">
        <div className="map-panel">
          <ComposableMap projection="geoAlbersUsa" className="usa-map">
            <Geographies geography={US_STATES_TOPO_JSON}>
              {({ geographies }) => geographies.map((geo) => {
                const code = FIPS_TO_STATE_CODE[String(geo.id).padStart(2, '0')];
                const stateName = code ? STATE_NAMES[code] ?? code : 'Unknown';

                return (
                  <Geography
                    key={geo.rsmKey}
                    geography={geo}
                    className="map-state"
                    onMouseEnter={() => code && setSelectedCode(code)}
                    onFocus={() => code && setSelectedCode(code)}
                    onClick={() => code && navigate(`/states/${code}`)}
                    aria-label={stateName}
                  />
                );
              })}
            </Geographies>
          </ComposableMap>
        </div>

        <aside className="hover-card" aria-live="polite">
          {!selectedCode ? <><h2>Select a state</h2><p>Choose a state on the map to see verified delegation data.</p></> : null}
          {loading ? <p>Loading delegation...</p> : null}
          {error ? <p>Delegation unavailable: {error}</p> : null}
          {timeline && !loading && !error ? <><h2>{timeline.state_name} ({timeline.state_code})</h2><p className="hover-label">119th Congress</p><p><strong>House:</strong> {timeline.house.groups?.[0]?.members.length ?? 0} member{(timeline.house.groups?.[0]?.members.length ?? 0) === 1 ? '' : 's'}</p><p><strong>Senate:</strong> {timeline.senate.groups?.[0]?.members.length ?? 0} members</p><button className="button" type="button" onClick={() => navigate(`/states/${timeline.state_code}`)}>Open state timeline</button></> : null}
        </aside>
      </div>
    </section>
  );
}