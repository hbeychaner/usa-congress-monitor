import { Badge, Button, Card, DataList, Flex, Grid, Heading, ScrollArea, Tabs, Text } from '@radix-ui/themes';
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { fetchBill, fetchBillVotes, type BillDetailResponse, type BillVotesResponse } from '../api/bills';
import { fetchBillTopics, type BillTopicsResponse } from '../api/topics';
import { SimilarBillsCard } from '../components/SimilarBillsCard';
import { ActionTimelineChart, type TimelineAction } from '../components/ActionTimelineChart';

type RecordValue = Record<string, unknown>;

const VISIBLE_ACTIONS = 10;
const DAY_LENGTH = 10;
const COSPONSOR_LIST_HEIGHT = 280;

function formatDate(value: string | null | undefined): string {
    if (!value) return 'Not recorded';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
}

function displayName(sponsor: RecordValue): string {
    return String(sponsor.full_name ?? sponsor.name ?? sponsor.id ?? 'Unknown sponsor');
}

function decodeEntities(value: string): string {
    if (!value.includes('&')) return value;
    return new DOMParser().parseFromString(value, 'text/html').documentElement.textContent ?? value;
}

function stripHtml(value: string): string {
    return decodeEntities(value.replace(/<[^>]*>/g, ' ')).replace(/\s+/g, ' ').trim();
}

function asRecords(value: unknown): RecordValue[] {
    return Array.isArray(value) ? (value.filter((item) => item && typeof item === 'object') as RecordValue[]) : [];
}

function uniquePeople(people: RecordValue[]): RecordValue[] {
    const seen = new Set<string>();
    return people.filter((person) => {
        const key = String(person.bioguide_id ?? displayName(person));
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
    });
}

function PersonName({ person }: { person: RecordValue }) {
    const name = <Text weight="bold">{displayName(person)}</Text>;
    return person.bioguide_id ? <Link to={`/members/${String(person.bioguide_id)}`}>{name}</Link> : name;
}

function dayOf(value: unknown): string {
    return String(value ?? '').slice(0, DAY_LENGTH);
}

// Committees (or subcommittees) with a recorded activity on the same day as an action.
function committeesOnDay(committees: RecordValue[], day: string): RecordValue[] {
    if (!day) return [];
    const matches: RecordValue[] = [];
    for (const committee of committees) {
        for (const entry of [committee, ...asRecords(committee.subcommittees)]) {
            if (entry.system_code && asRecords(entry.activities).some((activity) => dayOf(activity.date) === day)) {
                matches.push(entry);
            }
        }
    }
    return matches;
}

function CommitteeLink({ committee }: { committee: RecordValue }) {
    const name = String(committee.name ?? 'Unnamed committee');
    return committee.system_code ? <Link to={`/committees/${String(committee.system_code)}`}>{name}</Link> : <>{name}</>;
}

function tabLabel(name: string, count: number): string {
    return count > 0 ? `${name} (${count})` : name;
}

function Empty({ children }: { children: string }) {
    return <Text as="p" color="gray">{children}</Text>;
}

export function BillDetailPage() {
    const { billId = '' } = useParams();
    const [response, setResponse] = useState<BillDetailResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [votesResponse, setVotesResponse] = useState<BillVotesResponse | null>(null);
    const [topicsResponse, setTopicsResponse] = useState<BillTopicsResponse | null>(null);
    const [showAllActions, setShowAllActions] = useState(false);

    useEffect(() => {
        setResponse(null);
        setError(null);
        setShowAllActions(false);
        fetchBill(billId).then(setResponse).catch((err: Error) => setError(err.message));
    }, [billId]);

    useEffect(() => {
        setVotesResponse(null);
        fetchBillVotes(billId).then(setVotesResponse).catch(() => setVotesResponse(null));
    }, [billId]);

    useEffect(() => {
        setTopicsResponse(null);
        fetchBillTopics(billId).then(setTopicsResponse).catch(() => setTopicsResponse(null));
    }, [billId]);

    if (error) {
        return (
            <Card size="3">
                <Heading size="5" mb="1">Bill unavailable</Heading>
                <Text as="p">{error}</Text>
                <Link to="/bills">Back to bills</Link>
            </Card>
        );
    }
    if (!response) return <Card size="3"><Text as="p">Loading bill...</Text></Card>;

    const bill = response.bill;
    const action = bill.latest_action as RecordValue | null;
    const subjectsRaw = bill.subjects as RecordValue | null | undefined;
    const subjects = asRecords(subjectsRaw?.legislative_subjects ?? subjectsRaw?.legislativeSubjects);
    const sponsors = uniquePeople(bill.sponsors ?? []);
    const cosponsors = uniquePeople(asRecords(bill.cosponsors));
    const actions = asRecords(bill.actions);
    const summaries = asRecords(bill.summaries);
    const textVersions = asRecords(bill.text_versions);
    const committees = asRecords(bill.committees);
    const relatedBills = asRecords(bill.related_bills);
    const relationshipCounts = bill.relationship_counts ?? {};
    const votes = votesResponse?.votes ?? [];
    const visibleActions = showAllActions ? actions : actions.slice(0, VISIBLE_ACTIONS);
    const timelineActions: TimelineAction[] = actions.map((item) => ({
        date: String(item.action_date ?? ''),
        text: String(item.text ?? 'Action text not recorded'),
        source: item.source_system ? String((item.source_system as RecordValue).name ?? '') || undefined : undefined,
    }));

    return (
        <Flex direction="column" gap="4">
            <Link to="/bills">Back to bills</Link>
            <Flex justify="between" align="start" wrap="wrap" gap="3">
                <Flex direction="column" gap="1" style={{ flex: '1 1 480px' }}>
                    <Text size="1" color="gray">{bill.bill_type ?? 'Bill'} {bill.number ?? ''} · Congress {bill.congress ?? 'Unknown'}</Text>
                    <Heading size="7">{bill.title}</Heading>
                    <Text color="gray">
                        {[
                            bill.origin_chamber ?? 'Chamber not recorded',
                            `Introduced ${formatDate(bill.introduced_date)}`,
                            sponsors.length ? `Sponsor ${displayName(sponsors[0])}` : '',
                            `Updated ${formatDate(bill.update_date)}`,
                        ].filter(Boolean).join(' · ')}
                    </Text>
                    <Flex gap="1" wrap="wrap" mt="1">
                        {bill.policy_area ? (
                            <Badge asChild>
                                <Link to={`/bills?subject=${encodeURIComponent(bill.policy_area)}`}>{bill.policy_area}</Link>
                            </Badge>
                        ) : null}
                        {(topicsResponse?.topics ?? []).map((topic) => (
                            <Badge key={topic.topic_id} variant="soft" title={`Confidence ${Math.round(topic.probability * 100)}%`} style={{ textTransform: 'capitalize' }} asChild>
                                <Link to={`/topics/${topic.topic_id}`}>{topic.label}</Link>
                            </Badge>
                        ))}
                    </Flex>
                </Flex>
                <Button asChild>
                    <a href={`https://www.congress.gov/bill/${bill.congress}/${(bill.bill_type ?? '').toLowerCase()}/${bill.number}`} target="_blank" rel="noreferrer">View on Congress.gov</a>
                </Button>
            </Flex>

            <Card size="2" variant="surface">
                {action ? (
                    <Flex gap="3" align="baseline" wrap="wrap">
                        <Text size="2" weight="bold">Latest action · {formatDate(String(action.action_date ?? ''))}</Text>
                        <Text size="2" color="gray" style={{ flex: '1 1 320px' }}>{String(action.text ?? 'Action text not recorded')}</Text>
                    </Flex>
                ) : <Text size="2" color="gray">No action is recorded for this bill.</Text>}
            </Card>

            <Grid columns={{ initial: '1', md: '3' }} gap="4" align="start">
                <Card size="3" style={{ gridColumn: 'span 2' }}>
                    <Tabs.Root defaultValue="text" key={billId}>
                        <Tabs.List>
                            <Tabs.Trigger value="text">Text</Tabs.Trigger>
                            <Tabs.Trigger value="summary">Summary</Tabs.Trigger>
                            <Tabs.Trigger value="actions">{tabLabel('Actions', actions.length)}</Tabs.Trigger>
                            <Tabs.Trigger value="votes">{tabLabel('Votes', votes.length)}</Tabs.Trigger>
                            <Tabs.Trigger value="related">{tabLabel('Related', relatedBills.length)}</Tabs.Trigger>
                        </Tabs.List>

                        <Flex pt="4" direction="column">
                            <Tabs.Content value="summary">
                                <Flex direction="column" gap="4">
                                    {summaries.length ? summaries.map((summary, index) => (
                                        <Flex direction="column" gap="1" key={`${String(summary.version_code ?? index)}`}>
                                            <Text size="1" color="gray">{String(summary.action_desc ?? 'Summary')} · {formatDate(String(summary.action_date ?? ''))}</Text>
                                            <Text as="p">{stripHtml(String(summary.text ?? ''))}</Text>
                                        </Flex>
                                    )) : <Empty>No summaries are indexed for this bill.</Empty>}
                                    {subjects.length > 0 ? (
                                        <Flex direction="column" gap="2">
                                            <Heading size="3">Legislative subjects</Heading>
                                            <Flex gap="1" wrap="wrap">
                                                {subjects.map((subject, index) => {
                                                    const name = String(subject.name ?? subject.title ?? 'Unnamed subject');
                                                    return (
                                                        <Badge variant="soft" key={`${name}-${index}`} asChild>
                                                            <Link to={`/bills?subject=${encodeURIComponent(name)}`}>{name}</Link>
                                                        </Badge>
                                                    );
                                                })}
                                            </Flex>
                                        </Flex>
                                    ) : null}
                                </Flex>
                            </Tabs.Content>

                            <Tabs.Content value="actions">
                                {actions.length ? (
                                    <Flex direction="column" gap="3">
                                        <ActionTimelineChart actions={timelineActions} />
                                        {visibleActions.map((item, index) => (
                                            <Flex direction="column" gap="1" key={`${String(item.action_date ?? '')}-${index}`}>
                                                <Text size="1" weight="bold">{formatDate(String(item.action_date ?? ''))}{item.source_system && (item.source_system as RecordValue).name ? ` · ${String((item.source_system as RecordValue).name)}` : ''}</Text>
                                                <Text size="2">{String(item.text ?? 'Action text not recorded')}</Text>
                                                {committeesOnDay(committees, dayOf(item.action_date)).map((committee) => (
                                                    <Text size="1" key={String(committee.system_code)}>Committee: <CommitteeLink committee={committee} /></Text>
                                                ))}
                                            </Flex>
                                        ))}
                                        {actions.length > VISIBLE_ACTIONS ? (
                                            <Button variant="soft" onClick={() => setShowAllActions((value) => !value)}>
                                                {showAllActions ? 'Show fewer actions' : `Show all ${actions.length} actions`}
                                            </Button>
                                        ) : null}
                                    </Flex>
                                ) : <Empty>No actions are indexed for this bill.</Empty>}
                            </Tabs.Content>

                            <Tabs.Content value="votes">
                                {votes.length > 0 ? (
                                    <Flex direction="column" gap="4">
                                        {votes.map((vote) => (
                                            <Flex direction="column" gap="1" key={vote.vote_id}>
                                                <Flex justify="between" align="center" wrap="wrap" gap="2">
                                                    <Text weight="bold">{vote.question ?? 'Roll call vote'}</Text>
                                                    {vote.result ? <Badge color={vote.result === 'Passed' ? 'green' : 'red'}>{vote.result}</Badge> : null}
                                                </Flex>
                                                <Text size="1" color="gray">
                                                    {formatDate(vote.date)} · {vote.chamber} Roll Call {vote.roll_call_number ?? 'Unknown'} · {vote.vote_type ?? 'Vote'}
                                                </Text>
                                                <Text size="2">
                                                    Yea {vote.totals.yea} · Nay {vote.totals.nay} · Present {vote.totals.present} · Not Voting {vote.totals.not_voting}
                                                </Text>
                                                {vote.url ? (
                                                    <Text size="1"><a href={vote.url} target="_blank" rel="noreferrer">View vote details</a></Text>
                                                ) : null}
                                            </Flex>
                                        ))}
                                    </Flex>
                                ) : <Empty>No recorded votes are indexed for this bill.</Empty>}
                            </Tabs.Content>

                            <Tabs.Content value="text">
                                <Flex direction="column" gap="4">
                                    {textVersions.length ? (
                                        <Flex direction="column" gap="2">
                                            <Heading size="3">Versions</Heading>
                                            {textVersions.map((version, index) => (
                                                <Flex gap="3" align="baseline" wrap="wrap" key={`${String(version.type ?? version.date ?? index)}`}>
                                                    <Text weight="bold">{String(version.type ?? 'Text version')}</Text>
                                                    <Text size="1" color="gray">{formatDate(String(version.date ?? ''))}</Text>
                                                    {asRecords(version.formats).map((format) => (
                                                        <Text size="1" key={String(format.url ?? format.type)}>
                                                            <a href={String(format.url ?? '#')} target="_blank" rel="noreferrer">{String(format.type ?? 'Link')}</a>
                                                        </Text>
                                                    ))}
                                                </Flex>
                                            ))}
                                        </Flex>
                                    ) : <Empty>No text versions are indexed for this bill.</Empty>}
                                    {bill.full_text ? (
                                        <details>
                                            <summary><Text weight="medium">Full text{bill.full_text_version_code ? ` (version ${bill.full_text_version_code.toUpperCase()})` : ''}</Text></summary>
                                            <Text as="p" mt="2" style={{ whiteSpace: 'pre-wrap' }}>{decodeEntities(bill.full_text)}</Text>
                                        </details>
                                    ) : null}
                                </Flex>
                            </Tabs.Content>

                            <Tabs.Content value="related">
                                <Flex direction="column" gap="4">
                                    {relatedBills.length ? (
                                        <Flex direction="column" gap="3">
                                            {relatedBills.map((related, index) => {
                                                const relatedId = typeof related.id === 'string' ? related.id : null;
                                                const label = String(related.title ?? relatedId ?? `Related bill ${index + 1}`);
                                                const relationship = asRecords(related.relationship_details).map((detail) => String(detail.type ?? '')).filter(Boolean).join(', ');
                                                return (
                                                    <Flex direction="column" gap="1" key={relatedId ?? index}>
                                                        {relatedId ? <Link to={`/bills/${encodeURIComponent(relatedId)}`}><Text weight="bold">{label}</Text></Link> : <Text weight="bold">{label}</Text>}
                                                        <Text size="1" color="gray">{[related.congress ? `Congress ${related.congress}` : '', relationship].filter(Boolean).join(' · ')}</Text>
                                                    </Flex>
                                                );
                                            })}
                                        </Flex>
                                    ) : <Empty>No related bills are indexed for this bill.</Empty>}
                                    {Object.keys(relationshipCounts).length ? (
                                        <details>
                                            <summary><Text weight="medium">Available records</Text></summary>
                                            <DataList.Root mt="2">
                                                {Object.entries(relationshipCounts).map(([name, count]) => (
                                                    <DataList.Item key={name}>
                                                        <DataList.Label>{name.replace(/_/g, ' ')}</DataList.Label>
                                                        <DataList.Value>{count}</DataList.Value>
                                                    </DataList.Item>
                                                ))}
                                            </DataList.Root>
                                        </details>
                                    ) : null}
                                </Flex>
                            </Tabs.Content>
                        </Flex>
                    </Tabs.Root>
                </Card>

                <Flex direction="column" gap="4">
                    <Card size="3">
                        <Heading size="4" mb="2">Sponsors</Heading>
                        {sponsors.length ? (
                            <Flex direction="column" gap="2">
                                {sponsors.map((sponsor) => (
                                    <Flex direction="column" key={String(sponsor.id ?? displayName(sponsor))}>
                                        <PersonName person={sponsor} />
                                        {sponsor.party || sponsor.state ? (
                                            <Text size="1" color="gray">{[sponsor.party, sponsor.state, sponsor.district ? `District ${sponsor.district}` : ''].filter(Boolean).join(' · ')}</Text>
                                        ) : null}
                                    </Flex>
                                ))}
                            </Flex>
                        ) : <Empty>No sponsors are indexed for this bill.</Empty>}
                        <Heading size="3" mt="4" mb="2">Cosponsors {cosponsors.length ? `(${cosponsors.length})` : ''}</Heading>
                        {cosponsors.length ? (
                            <ScrollArea type="auto" scrollbars="vertical" style={{ maxHeight: COSPONSOR_LIST_HEIGHT }}>
                                <Flex direction="column" gap="2" pr="3">
                                    {cosponsors.map((cosponsor) => (
                                        <Flex direction="column" key={String(cosponsor.bioguide_id ?? displayName(cosponsor))}>
                                            <PersonName person={cosponsor} />
                                            <Text size="1" color="gray">
                                                {[cosponsor.party, cosponsor.state, cosponsor.is_original_cosponsor ? 'Original cosponsor' : '', cosponsor.sponsorship_date ? `Joined ${formatDate(String(cosponsor.sponsorship_date))}` : ''].filter(Boolean).join(' · ')}
                                            </Text>
                                        </Flex>
                                    ))}
                                </Flex>
                            </ScrollArea>
                        ) : <Empty>No cosponsors are indexed for this bill.</Empty>}
                    </Card>
                    <Card size="3">
                        <Heading size="4" mb="2">Committees</Heading>
                        {committees.length ? (
                            <Flex direction="column" gap="2">
                                {committees.map((committee, index) => (
                                    <Flex direction="column" key={String(committee.system_code ?? index)}>
                                        <Text weight="bold"><CommitteeLink committee={committee} /></Text>
                                        {committee.chamber ? <Text size="1" color="gray">{String(committee.chamber)}</Text> : null}
                                    </Flex>
                                ))}
                            </Flex>
                        ) : <Empty>No committee referrals are indexed for this bill.</Empty>}
                    </Card>
                    <SimilarBillsCard billId={billId} />
                </Flex>
            </Grid>
        </Flex>
    );
}
