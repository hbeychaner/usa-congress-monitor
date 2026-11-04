const enactedLawVersion = /^(public|private)-law-([1-9]\d*)-([1-9]\d*)$/;

export function isEnactedLawText(version: string | null | undefined): boolean {
    return enactedLawVersion.test(version ?? '');
}

export function billTextHeading(version: string | null | undefined): string {
    const law = enactedLawVersion.exec(version ?? '');
    if (law) return `Enacted ${law[1]} law text (${law[2]}-${law[3]})`;
    return `Full text${version ? ` (version ${version.toUpperCase()})` : ''}`;
}
