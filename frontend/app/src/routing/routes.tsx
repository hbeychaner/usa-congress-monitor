import { Suspense, lazy } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import { HomePage } from '../pages/HomePage';

const AdminIngestPage = lazy(() =>
  import('../pages/AdminIngestPage').then((m) => ({ default: m.AdminIngestPage })),
);
const BillDetailPage = lazy(() =>
  import('../pages/BillDetailPage').then((m) => ({ default: m.BillDetailPage })),
);
const BillsPage = lazy(() =>
  import('../pages/BillsPage').then((m) => ({ default: m.BillsPage })),
);
const CommitteeDetailPage = lazy(() =>
  import('../pages/CommitteeDetailPage').then((m) => ({ default: m.CommitteeDetailPage })),
);
const MemberGraphPage = lazy(() =>
  import('../pages/MemberGraphPage').then((m) => ({ default: m.MemberGraphPage })),
);
const MemberProfilePage = lazy(() =>
  import('../pages/MemberProfilePage').then((m) => ({ default: m.MemberProfilePage })),
);
const MemberSearchPage = lazy(() =>
  import('../pages/MemberSearchPage').then((m) => ({ default: m.MemberSearchPage })),
);
const PartiesPage = lazy(() =>
  import('../pages/PartiesPage').then((m) => ({ default: m.PartiesPage })),
);
const SearchPage = lazy(() =>
  import('../pages/SearchPage').then((m) => ({ default: m.SearchPage })),
);
const StateDetailPage = lazy(() =>
  import('../pages/StateDetailPage').then((m) => ({ default: m.StateDetailPage })),
);
const StatesPage = lazy(() =>
  import('../pages/StatesPage').then((m) => ({ default: m.StatesPage })),
);
const TopicDetailPage = lazy(() =>
  import('../pages/TopicDetailPage').then((m) => ({ default: m.TopicDetailPage })),
);
const TopicsPage = lazy(() =>
  import('../pages/TopicsPage').then((m) => ({ default: m.TopicsPage })),
);

export function AppRoutes() {
  return (
    <Suspense fallback={null}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/admin/ingest" element={<AdminIngestPage />} />
        <Route path="/states" element={<StatesPage />} />
        <Route path="/states/:stateCode" element={<StateDetailPage />} />
        <Route path="/members" element={<MemberSearchPage />} />
        <Route path="/members/:bioguideId" element={<MemberProfilePage />} />
        <Route path="/graph" element={<MemberGraphPage />} />
        <Route path="/bills" element={<BillsPage />} />
        <Route path="/bills/:billId" element={<BillDetailPage />} />
        <Route path="/committees/:systemCode" element={<CommitteeDetailPage />} />
        <Route path="/topics" element={<TopicsPage />} />
        <Route path="/topics/:topicId" element={<TopicDetailPage />} />
        <Route path="/parties" element={<PartiesPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
