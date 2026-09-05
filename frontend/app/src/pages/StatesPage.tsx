import { Button, Card, Flex, Heading, Text } from '@radix-ui/themes';
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
    <Flex direction="column" gap="5">
      <Flex direction="column" gap="2">
        <Heading size="7">States</Heading>
        <Text color="gray">Select a state to preview its 119th Congress delegation. Open the state for its full history.</Text>
      </Flex>

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

        <Card size="3" asChild>
          <aside aria-live="polite">
            <Flex direction="column" gap="2">
              {!selectedCode ? (
                <>
                  <Heading size="4">Select a state</Heading>
                  <Text color="gray">Choose a state on the map to see verified delegation data.</Text>
                </>
              ) : null}
              {loading ? <Text as="p">Loading delegation...</Text> : null}
              {error ? <Text as="p">Delegation unavailable: {error}</Text> : null}
              {timeline && !loading && !error ? (
                <>
                  <Heading size="4">{timeline.state_name} ({timeline.state_code})</Heading>
                  <Text size="1" color="gray">119th Congress</Text>
                  <Text as="p"><Text weight="bold">House:</Text> {timeline.house.groups?.[0]?.members.length ?? 0} member{(timeline.house.groups?.[0]?.members.length ?? 0) === 1 ? '' : 's'}</Text>
                  <Text as="p"><Text weight="bold">Senate:</Text> {timeline.senate.groups?.[0]?.members.length ?? 0} members</Text>
                  <Button onClick={() => navigate(`/states/${timeline.state_code}`)}>Open state timeline</Button>
                </>
              ) : null}
            </Flex>
          </aside>
        </Card>
      </div>
    </Flex>
  );
}
