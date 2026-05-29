/* ============================================
   Config — API 配置和常量
   ============================================ */

const API_BASE = 'http://192.168.23.26:8000';

const PAGE_TITLES = {
  dashboard: '工作台',
  trigger: '触发分析',
  referral: '转介绍检测',
  cases: '优秀话术提取',
  success: '成功案例分析结果',
  followup: '督学跟进合规',
  scriptlib: '话术库',
  rag: 'RAG 问答',
  agents: '智能体管理',
};

const AGENT_OPTIONS = [
  { value: 'all', label: '全部智能体（4个同时执行）' },
  { value: 'referral', label: '转介绍检测' },
  { value: 'case', label: '优秀话术提炼' },
  { value: 'journey', label: '优秀成交案例分析' },
  { value: 'follow_up', label: '督学跟进合规检测' },
];

const AGENT_NAMES = {
  referral: '转介绍检测',
  case: '优秀话术提取',
  journey: '优秀成交案例提取',
  follow_up: '督学跟进合规检测',
};

// Pagination defaults
const PAGE_SIZE = {
  referral: 20,
  cases: 12,
  success: 12,
  followup: 20,
  salesjourney: 12,
  scriptlib: 16,
};
