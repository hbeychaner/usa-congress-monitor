import { Badge, Button, Card, DataList, Flex, Grid, Heading, Text } from '@radix-ui/themes';
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { fetchBill, fetchBillVotes, type BillDetailResponse, type BillVotesResponse } from '../api/bills';
import { fetchBillTopics, type BillTopicsResponse } from '../api/topics';

type RecordValue = Record<string, unknown>;

function formatDate(value: string | null | undefined): string {
    if (!value) return 'Not recorded';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
}

function displayName(sponsor: RecordValue): string {
    return String(sponsor.full_name ?? sponsor.name ?? sponsor.id ?? 'Unknown sponsor');
}

function stripHtml(value: string): string {
    return value.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
}

function asRecords(value: unknown): RecordValue[] {
    return Array.isArray(value) ? (value.filter((item) => item && typeof item === 'object') as RecordValue[]) : [];
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
    const sponsors = bill.sponsors ?? [];
    const cosponsors = asRecords(bill.cosponsors);
    const actions = asRecords(bill.actions);
    const summaries = asRecords(bill.summaries);
    const textVersions = asRecords(bill.text_versions);
    const committees = asRecords(bill.committees);
    const relatedBills = asRecords(bill.related_bills);
    const relationshipCounts = bill.relationship_counts ?? {};
    const visibleActions = showAllActions ? actions : actions.slice(0, 8);

    return (
        <Flex direction="column" gap="5">
            <Link to="/bills">Back to bills</Link>
            <Flex justify="between" align="start" wrap="wrap" gap="3">
                <Flex direction="column" gap="1">
                    <Text size="1" color="gray">{bill.bill_type ?? 'Bill'} {bill.number ?? ''} · Congress {bill.congress ?? 'Unknown'}</Text>
                    <Heading size="7">{bill.title}</Heading>
                    <Text color="gray">{bill.origin_chamber ?? 'Chamber not recorded'} · Introduced {formatDate(bill.introduced_date)}</Text>
                    {topicsResponse && topicsResponse.topics.length > 0 ? (
                        <Flex gap="1" wrap="wrap" mt="1">
                            {topicsResponse.topics.map((topic) => (
                                <Badge key={topic.topic_id} variant="soft" title={`Confidence ${Math.round(topic.probability * 100)}%`} style={{ textTransform: 'capitalize' }} asChild>
                                    <Link to={`/topics/${topic.topic_id}`}>{topic.label}</Link>
                                </Badge>
                            ))}
                        </Flex>
                    ) : null}
                </Flex>
                <Button asChild>
                    <a href={`https://www.congress.gov/bill/${bill.congress}/${(bill.bill_type ?? '').toLowerCase()}/${bill.number}`} target="_blank" rel="noreferrer">View on Congress.gov</a>
                </Button>
            </Flex>

            <Grid columns={{ initial: '1', md: '3' }} gap="4">
                <Flex direction="column" gap="4" style={{ gridColumn: 'span 2' }}>
                    <Card size="3">
                        <Heading size="4" mb="2">Latest action</Heading>
                        {action ? (
                            <Flex direction="column" gap="1">
                                <Text weight="bold">{formatDate(String(action.action_date ?? ''))}</Text>
                                <Text color="gray">{String(action.text ?? 'Action text not recorded')}</Text>
                            </Flex>
                        ) : <Text as="p" color="gray">No action is recorded for this bill.</Text>}
                    </Card>
                    <Card size="3">
                        <Heading size="4" mb="2">Action history</Heading>
                        {actions.length ? (
                            <Flex direction="column" gap="3">
                                {visibleActions.map((item, index) => (
                                    <Flex direction="column" gap="1" key={`${String(item.action_date ?? '')}-${index}`}>
                                        <Text size="1" weight="bold">{formatDate(String(item.action_date ?? ''))}{item.source_system && (item.source_system as RecordValue).name ? ` · ${String((item.source_system as RecordValue).name)}` : ''}</Text>
                                        <Text size="2">{String(item.text ?? 'Action text not recorded')}</Text>
                                    </Flex>
                                ))}
                                {actions.length > 8 ? (
                                    <Button variant="soft" onClick={() => setShowAllActions((value) => !value)}>
                                        {showAllActions ? 'Show fewer actions' : `Show all ${actions.length} actions`}
                                    </Button>
                                ) : null}
                            </Flex>
                        ) : <Text as="p" color="gray">No actions are indexed for this bill.</Text>}
                    </Card>
                    <Card size="3">
                        <Heading size="4" mb="2">Summaries</Heading>
                        {summaries.length ? (
                            <Flex direction="column" gap="3">
                                {summaries.map((summary, index) => (
                                    <Flex direction="column" gap="1" key={`${String(summary.version_code ?? index)}`}>
                                        <Text size="1" color="gray">{String(summary.action_desc ?? 'Summary')} · {formatDate(String(summary.action_date ?? ''))}</Text>
                                        <Text as="p">{stripHtml(String(summary.text ?? ''))}</Text>
                                    </Flex>
                                ))}
                            </Flex>
                        ) : <Text as="p" color="gray">No summaries are indexed for this bill.</Text>}
                    </Card>
                    <Card size="3">
                        <Heading size="4" mb="2">Policy and subjects</Heading>
                        {bill.policy_area ? <Badge mb="2">{bill.policy_area}</Badge> : <Text as="p" color="gray">Policy area not recorded.</Text>}
                        {subjects.length > 0 ? (
                            <Flex direction="column" gap="1" mt="2">
                                {subjects.map((subject, index) => (
                                    <Text as="p" key={`${String(subject.name ?? subject.title ?? index)}`}>
                                        {String(subject.name ?? subject.title ?? 'Unnamed subject')}
                                    </Text>
                                ))}
                            </Flex>
                        ) : <Text as="p" color="gray">Legislative subjects are not expanded in this record.</Text>}
                    </Card>
                    {bill.full_text ? (
                        <Card size="3" asChild>
                            <details>
                                <summary><Text weight="medium">Bill text{bill.full_text_version_code ? ` (version ${bill.full_text_version_code.toUpperCase()})` : ''}</Text></summary>
                                <Text as="p" mt="2" style={{ whiteSpace: 'pre-wrap' }}>{bill.full_text}</Text>
                            </details>
                        </Card>
                    ) : null}
                    <Card size="3">
                        <Heading size="4" mb="2">Roll call votes</Heading>
                        {votesResponse && votesResponse.votes.length > 0 ? (
                            <Flex direction="column" gap="3">
                                {votesResponse.votes.map((vote) => (
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
                        ) : <Text as="p" color="gray">No recorded votes are indexed for this bill.</Text>}
                    </Card>
                </Flex>

                <Flex direction="column" gap="4">
                    <Card size="3">
                        <Heading size="4" mb="2">Bill record</Heading>
                        <DataList.Root>
                            <DataList.Item><DataList.Label>Type</DataList.Label><DataList.Value>{bill.bill_type ?? 'Not recorded'}</DataList.Value></DataList.Item>
                            <DataList.Item><DataList.Label>Number</DataList.Label><DataList.Value>{bill.number ?? 'Not recorded'}</DataList.Value></DataList.Item>
                            <DataList.Item><DataList.Label>Origin chamber</DataList.Label><DataList.Value>{bill.origin_chamber ?? 'Not recorded'}</DataList.Value></DataList.Item>
                            <DataList.Item><DataList.Label>Last updated</DataList.Label><DataList.Value>{formatDate(bill.update_date)}</DataList.Value></DataList.Item>
                        </DataList.Root>
                    </Card>
                    <Card size="3">
                        <Heading size="4" mb="2">Sponsors</Heading>
                        {sponsors.length ? (
                            <Flex direction="column" gap="2">
                                {sponsors.map((sponsor) => (
                                    <Flex direction="column" key={String(sponsor.id ?? displayName(sponsor))}>
                                        <Text weight="bold">{displayName(sponsor)}</Text>
                                        {sponsor.party || sponsor.state ? (
                                            <Text size="1" color="gray">{[sponsor.party, sponsor.state, sponsor.district ? `District ${sponsor.district}` : ''].filter(Boolean).join(' · ')}</Text>
                                        ) : null}
                                    </Flex>
                                ))}
                            </Flex>
                        ) : <Text as="p" color="gray">No sponsors are indexed for this bill.</Text>}
                    </Card>
                    <Card size="3">
                        <Heading size="4" mb="2">Cosponsors {cosponsors.length ? `(${cosponsors.length})` : ''}</Heading>
                        {cosponsors.length ? (
                            <Flex direction="column" gap="2">
                                {cosponsors.map((cosponsor) => (
                                    <Flex direction="column" key={String(cosponsor.bioguide_id ?? displayName(cosponsor))}>
                                        {cosponsor.bioguide_id ? (
                                            <Link to={`/members/${String(cosponsor.bioguide_id)}`}><Text weight="bold">{displayName(cosponsor)}</Text></Link>
                                        ) : <Text weight="bold">{displayName(cosponsor)}</Text>}
                                        <Text size="1" color="gray">
                                            {[cosponsor.party, cosponsor.state, cosponsor.is_original_cosponsor ? 'Original cosponsor' : '', cosponsor.sponsorship_date ? `Joined ${formatDate(String(cosponsor.sponsorship_date))}` : ''].filter(Boolean).join(' · ')}
                                        </Text>
                                    </Flex>
                                ))}
                            </Flex>
                        ) : <Text as="p" color="gray">No cosponsors are indexed for this bill.</Text>}
                    </Card>
                    <Card size="3">
                        <Heading size="4" mb="2">Committees</Heading>
                        {committees.length ? (
                            <Flex direction="column" gap="2">
                                {committees.map((committee, index) => (
                                    <Flex direction="column" key={String(committee.system_code ?? index)}>
                                        <Text weight="bold">{String(committee.name ?? 'Unnamed committee')}</Text>
                                        {committee.chamber ? <Text size="1" color="gray">{String(committee.chamber)}</Text> : null}
                                    </Flex>
                                ))}
                            </Flex>
                        ) : <Text as="p" color="gray">No committee referrals are indexed for this bill.</Text>}
                    </Card>
                    <Card size="3">
                        <Heading size="4" mb="2">Text versions</Heading>
                        {textVersions.length ? (
                            <Flex direction="column" gap="2">
                                {textVersions.map((version, index) => (
                                    <Flex direction="column" gap="1" key={`${String(version.type ?? version.date ?? index)}`}>
                                        <Text weight="bold">{String(version.type ?? 'Text version')}</Text>
                                        <Text size="1" color="gray">{formatDate(String(version.date ?? ''))}</Text>
                                        <Flex gap="2" wrap="wrap">
                                            {asRecords(version.formats).map((format) => (
                                                <Text size="1" key={String(format.url ?? format.type)}>
                                                    <a href={String(format.url ?? '#')} target="_blank" rel="noreferrer">{String(format.type ?? 'Link')}</a>
                                                </Text>
                                            ))}
                                        </Flex>
                                    </Flex>
                                ))}
                            </Flex>
                        ) : <Text as="p" color="gray">No text versions are indexed for this bill.</Text>}
                    </Card>
                    <Card size="3">
                        <Heading size="4" mb="2">Related bills</Heading>
                        {relatedBills.length ? (
                            <Flex direction="column" gap="2">
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
                        ) : <Text as="p" color="gray">No related bills are indexed for this bill.</Text>}
                    </Card>
                    <Card size="3">
                        <Heading size="4" mb="2">Available records</Heading>
                        {Object.keys(relationshipCounts).length ? (
                            <DataList.Root>
                                {Object.entries(relationshipCounts).map(([name, count]) => (
                                    <DataList.Item key={name}>
                                        <DataList.Label>{name.replace(/_/g, ' ')}</DataList.Label>
                                        <DataList.Value>{count}</DataList.Value>
                                    </DataList.Item>
                                ))}
                            </DataList.Root>
                        ) : <Text as="p" color="gray">No related record counts are available.</Text>}
                    </Card>
                </Flex>
            </Grid>
        </Flex>
    );
}
