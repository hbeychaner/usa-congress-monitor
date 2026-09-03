import { Navigate, Route, Routes } from 'react-router-dom';

import { AdminIngestPage } from '../pages/AdminIngestPage';
import { BillDetailPage } from '../pages/BillDetailPage';
import { BillsPage } from '../pages/BillsPage';
import { HomePage } from '../pages/HomePage';
import { MemberProfilePage } from '../pages/MemberProfilePage';
import { MemberSearchPage } from '../pages/MemberSearchPage';
import { SearchPage } from '../pages/SearchPage';
import { StateDetailPage } from '../pages/StateDetailPage';
import { StatesPage } from '../pages/StatesPage';
import { TopicDetailPage } from '../pages/TopicDetailPage';
import { TopicsPage } from '../pages/TopicsPage';

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/admin/ingest" element={<AdminIngestPage />} />
      <Route path="/states" element={<StatesPage />} />
      <Route path="/states/:stateCode" element={<StateDetailPage />} />
      <Route path="/members" element={<MemberSearchPage />} />
      <Route path="/members/:bioguideId" element={<MemberProfilePage />} />
      <Route path="/bills" element={<BillsPage />} />
      <Route path="/bills/:billId" element={<BillDetailPage />} />
      <Route path="/topics" element={<TopicsPage />} />
      <Route path="/topics/:topicLabel" element={<TopicDetailPage />} />
      <Route path="/search" element={<SearchPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
