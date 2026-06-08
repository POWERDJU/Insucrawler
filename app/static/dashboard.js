const state = {
  options: null,
  lastQuery: null,
  products: [],
  selectedProductId: null,
  monthlyProducts: [],
  monthlyIndex: 0,
  monthlyTimer: null,
  exclusiveRights: [],
  exclusiveIndex: 0,
  exclusiveTimer: null,
  exclusiveRightList: [],
  exclusiveRightListLoaded: false,
  exclusiveRightListUserTouched: false,
  activeMobileView: "products",
  mobileOverlayNames: {
    productFilter: "mobile-product-filter",
    exclusiveFilter: "mobile-exclusive-filter",
    productDetail: "mobile-product-detail",
  },
  adminToken: sessionStorage.getItem("adminToken") || null,
  adminPollTimer: null,
};
const NO_SELECTION = "__NO_SELECTION__";

const LABELS = {
  product_id: "상품 ID",
  company_name: "보험회사",
  insurance_type: "업종",
  subject_name: "상품/특약/제도명",
  exclusivity_months: "기간",
  acquired_year_month: "획득년월",
  feature_summary: "주요 특징",
  primary_article_title: "대표 기사",
  release_year_month: "출시년월",
  product_type_code: "상품군 코드",
  product_type_name: "보종군",
  normalized_product_name: "상품명",
  raw_product_name: "상품명 원문",
  primary_product_type: "대표 보종군",
  coverage_summary: "주요보장 요약",
  major_coverage_count: "주요보장 수",
  article_count: "관련기사 수",
  confidence_total: "confidence",
  needs_review: "검수필요 여부",
  crawl_job_id: "작업 ID",
  job_name: "작업명",
  job_type: "유형",
  status: "상태",
  date_from: "시작일",
  date_to: "종료일",
  total_tasks: "전체 task",
  completed_tasks: "완료 task",
  failed_tasks: "실패 task",
  total_api_calls: "API 호출",
  total_items_fetched: "조회 건수",
  total_articles_saved: "저장 기사",
  total_articles_duplicated: "중복 기사",
  total_articles_out_of_range: "기간외",
  started_at: "시작시각",
  finished_at: "종료시각",
  error_message: "오류",
  crawl_task_id: "Task ID",
  company_name: "보험회사",
  query_text: "검색어",
  api_calls: "API 호출",
  items_fetched: "조회 건수",
  articles_saved: "저장 기사",
  articles_duplicated: "중복 기사",
  articles_out_of_range: "기간외",
  last_error: "오류",
  llm_batch_job_id: "Batch ID",
  provider: "Provider",
  model_name: "모델",
  task_type: "작업유형",
  provider_batch_id: "Provider Batch ID",
  provider_status: "Provider 상태",
  request_count: "요청 수",
  completed_count: "완료 수",
  failed_count: "실패 수",
  submitted_at: "제출시각",
  completed_at: "완료시각",
  llm_queue_id: "Queue ID",
  target_type: "대상유형",
  target_id: "대상 ID",
  priority: "우선순위",
};

document.addEventListener("DOMContentLoaded", async () => {
  bindEvents();
  await loadOptions();
  syncDesktopFiltersToMobile();
  await loadMonthlyNewProducts();
  await loadRecentExclusiveRights();
  initExclusiveRightListFilters();
  syncDesktopExclusiveFiltersToMobile();
  await loadExclusiveRightList();
  await refreshDemoStatus();
  await runQuery();
});

function bindEvents() {
  document.getElementById("runQuery").addEventListener("click", runQuery);
  document.getElementById("downloadExcel").addEventListener("click", downloadExcel);
  document.getElementById("keywordInput")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      runQuery();
    }
  });
  document.getElementById("insuranceType").addEventListener("change", async () => {
    fillCompanyCheckboxes(new Set(), { selectAllWhenEmpty: true });
    syncDesktopFiltersToMobile();
    await loadMonthlyNewProducts();
    await loadRecentExclusiveRights();
    if (!state.exclusiveRightListUserTouched) {
      syncExclusiveRightListInsuranceType();
      syncDesktopExclusiveFiltersToMobile();
      await loadExclusiveRightList();
    }
    await runQuery();
  });
  document.getElementById("exclusiveRightSearch")?.addEventListener("click", async () => {
    state.exclusiveRightListUserTouched = true;
    await loadExclusiveRightList();
  });
  document.getElementById("exclusiveRightExcelDownload")?.addEventListener("click", downloadExclusiveRightsExcel);
  document.getElementById("exclusiveRightInsuranceType")?.addEventListener("change", () => {
    state.exclusiveRightListUserTouched = true;
    fillExclusiveRightCompanyCheckboxes(new Set(), { selectAllWhenEmpty: true });
  });
  document.getElementById("exclusiveRightKeyword")?.addEventListener("keydown", async (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      state.exclusiveRightListUserTouched = true;
      await loadExclusiveRightList();
    }
  });
  ["exclusiveRightPeriodPreset", "exclusiveRightMonthFrom", "exclusiveRightMonthTo"].forEach((id) => {
    document.getElementById(id)?.addEventListener("change", () => {
      state.exclusiveRightListUserTouched = true;
    });
  });
  document.getElementById("monthlyNext").addEventListener("click", (event) => {
    event.stopPropagation();
    nextMonthlyItem();
    startMonthlyBoardTimer();
  });
  document.getElementById("monthlyPrev").addEventListener("click", (event) => {
    event.stopPropagation();
    prevMonthlyItem();
    startMonthlyBoardTimer();
  });
  const monthlyCard = document.getElementById("monthlyBoardCard");
  monthlyCard.addEventListener("mouseenter", stopMonthlyBoardTimer);
  monthlyCard.addEventListener("focusin", stopMonthlyBoardTimer);
  monthlyCard.addEventListener("mouseleave", startMonthlyBoardTimer);
  monthlyCard.addEventListener("focusout", startMonthlyBoardTimer);
  document.getElementById("exclusiveNext")?.addEventListener("click", (event) => {
    event.stopPropagation();
    nextExclusiveItem();
    startExclusiveBoardTimer();
  });
  document.getElementById("exclusivePrev")?.addEventListener("click", (event) => {
    event.stopPropagation();
    prevExclusiveItem();
    startExclusiveBoardTimer();
  });
  const exclusiveCard = document.getElementById("exclusiveBoardCard");
  exclusiveCard?.addEventListener("mouseenter", stopExclusiveBoardTimer);
  exclusiveCard?.addEventListener("focusin", stopExclusiveBoardTimer);
  exclusiveCard?.addEventListener("mouseleave", startExclusiveBoardTimer);
  exclusiveCard?.addEventListener("focusout", startExclusiveBoardTimer);
  bindCheckboxGroup("releaseYearAll", "releaseYearOptions");
  bindCheckboxGroup("companyNamesAll", "companyNames");
  bindCheckboxGroup("productTypeCodesAll", "productTypeCodes");
  bindCheckboxGroup("exclusiveRightCompanyNamesAll", "exclusiveRightCompanyNames");
  document.getElementById("exclusiveRightCompanyNames")?.addEventListener("change", () => {
    state.exclusiveRightListUserTouched = true;
  });
  document.getElementById("closeDetail").addEventListener("click", () => {
    state.selectedProductId = null;
    renderProducts(state.products);
    document.getElementById("detailContent").innerHTML = '<div class="detail-empty">상품목록에서 상품명을 선택하세요.</div>';
  });
  initMobileLayout();
  bindAdminEvents();
}

function bindCheckboxGroup(allId, listId) {
  const allButton = document.getElementById(allId);
  const list = document.getElementById(listId);
  if (!allButton || !list) return;
  allButton.addEventListener("click", () => {
    if (allButton.disabled) return;
    const shouldSelectAll = !allItemsSelected(listId);
    setAllCheckboxes(listId, shouldSelectAll);
    syncSelectAllButton(allId, listId);
  });
  list.addEventListener("change", (event) => {
    if (!(event.target instanceof HTMLInputElement) || event.target.type !== "checkbox") return;
    syncSelectAllButton(allId, listId);
  });
}

async function loadOptions({ preserveSelections = false } = {}) {
  const selectedYears = new Set(preserveSelections ? selectedCheckboxValues("releaseYearOptions") : []);
  const selectedCompanies = new Set(preserveSelections ? selectedCheckboxValues("companyNames") : []);
  const selectedProductTypes = new Set(preserveSelections ? selectedCheckboxValues("productTypeCodes") : []);
  const selectedInsuranceType = preserveSelections ? document.getElementById("insuranceType").value : "";
  const options = await getJson(`/api/dashboard/options?${new URLSearchParams(optionFlags()).toString()}`);
  state.options = options;

  restoreSingleSelection("insuranceType", selectedInsuranceType);
  fillReleaseYearCheckboxes(selectedYears, { selectAllWhenEmpty: !preserveSelections });
  fillCompanyCheckboxes(selectedCompanies, { selectAllWhenEmpty: !preserveSelections });
  fillProductTypeCheckboxes(selectedProductTypes, { selectAllWhenEmpty: !preserveSelections });
}

async function refreshDemoStatus() {
  const status = await getJson("/api/dashboard/demo-status");
  const notice = document.getElementById("demoNotice");
  notice.hidden = Boolean(status.has_products);
}

async function loadMonthlyNewProducts() {
  const board = document.getElementById("monthlyNewProductBoard");
  if (!board) return;
  try {
    const params = new URLSearchParams({
      limit: "12",
      fallback_latest: "true",
      include_review: "false",
    });
    const insuranceType = document.getElementById("insuranceType")?.value;
    if (insuranceType) params.set("insurance_type", insuranceType);
    const result = await getJson(`/api/dashboard/monthly-new-products?${params.toString()}`);
    state.monthlyProducts = result.items || [];
    state.monthlyIndex = 0;
    renderMonthlyBoard(result);
    startMonthlyBoardTimer();
    if (isMobileViewport() && state.activeMobileView === "exclusive-rights") stopMonthlyBoardTimer();
  } catch (error) {
    state.monthlyProducts = [];
    stopMonthlyBoardTimer();
    document.getElementById("monthlyBoardCard").hidden = true;
    const empty = document.getElementById("monthlyBoardEmpty");
    empty.hidden = false;
    empty.textContent = `신상품 현황판을 불러오지 못했습니다: ${error.message}`;
  }
}

function renderMonthlyBoard(result) {
  const empty = document.getElementById("monthlyBoardEmpty");
  const card = document.getElementById("monthlyBoardCard");
  const items = state.monthlyProducts || [];
  document.getElementById("monthlyBoardTitle").textContent = result.fallback_used
    ? `${result.display_year_month} 신상품`
    : "이달의 신상품";
  if (!items.length) {
    empty.hidden = false;
    card.hidden = true;
    return;
  }
  empty.hidden = true;
  card.hidden = false;
  renderMonthlyItem();
}

function renderMonthlyItem() {
  const items = state.monthlyProducts || [];
  if (!items.length) return;
  const item = items[state.monthlyIndex % items.length];
  document.getElementById("monthlyCompany").textContent = item.company_name || "-";
  document.getElementById("monthlyType").textContent = item.primary_product_type || "-";
  document.getElementById("monthlyReleaseMonth").textContent = item.release_year_month || "-";
  document.getElementById("monthlyProductName").textContent = item.product_name || "-";
  document.getElementById("monthlySummary").textContent = item.summary || item.article_title || "";
  document.getElementById("monthlyArticleTitle").textContent = item.article_title || "";
  document.getElementById("monthlyPager").textContent = `${state.monthlyIndex + 1} / ${items.length}`;

  const card = document.getElementById("monthlyBoardCard");
  renderNewsboardLogo(card, "monthlyCompanyLogo", "monthlyLogoWrap", item.company_logo_url, item.company_name);
  if (item.article_url) {
    card.href = item.article_url;
    card.classList.remove("disabled");
    card.setAttribute("aria-label", `${item.product_name || "신상품"} 원문 기사 열기`);
  } else {
    card.removeAttribute("href");
    card.classList.add("disabled");
    card.setAttribute("aria-label", `${item.product_name || "신상품"} 원문 기사 URL 없음`);
  }
}

function renderNewsboardLogo(card, logoId, wrapId, logoUrl, companyName) {
  const logo = document.getElementById(logoId);
  const wrap = document.getElementById(wrapId);
  if (!card || !logo || !wrap) return;
  const hasLogo = Boolean(logoUrl);
  card.classList.toggle("has-logo", hasLogo);
  wrap.hidden = !hasLogo;
  logo.hidden = !hasLogo;
  logo.onerror = () => {
    logo.hidden = true;
    wrap.hidden = true;
    card.classList.remove("has-logo");
    logo.removeAttribute("src");
  };
  if (hasLogo) {
    logo.src = logoUrl;
    logo.alt = `${companyName || "보험회사"} 로고`;
  } else {
    logo.removeAttribute("src");
    logo.alt = "";
  }
}

function nextMonthlyItem() {
  if (!state.monthlyProducts.length) return;
  state.monthlyIndex = (state.monthlyIndex + 1) % state.monthlyProducts.length;
  renderMonthlyItem();
}

function prevMonthlyItem() {
  if (!state.monthlyProducts.length) return;
  state.monthlyIndex = (state.monthlyIndex - 1 + state.monthlyProducts.length) % state.monthlyProducts.length;
  renderMonthlyItem();
}

function startMonthlyBoardTimer() {
  stopMonthlyBoardTimer();
  if ((state.monthlyProducts || []).length <= 1) return;
  state.monthlyTimer = setInterval(nextMonthlyItem, 5000);
}

function stopMonthlyBoardTimer() {
  if (state.monthlyTimer) {
    clearInterval(state.monthlyTimer);
    state.monthlyTimer = null;
  }
}

async function loadRecentExclusiveRights() {
  const board = document.getElementById("recentExclusiveRightsBoard");
  if (!board) return;
  try {
    const params = new URLSearchParams({
      months_back: "12",
      limit: "12",
      include_review: "false",
    });
    const insuranceType = document.getElementById("insuranceType")?.value;
    if (insuranceType) params.set("insurance_type", insuranceType);
    const result = await getJson(`/api/dashboard/recent-exclusive-rights?${params.toString()}`);
    state.exclusiveRights = result.items || [];
    state.exclusiveIndex = 0;
    renderExclusiveBoard();
    startExclusiveBoardTimer();
    if (isMobileViewport() && state.activeMobileView !== "exclusive-rights") stopExclusiveBoardTimer();
  } catch (error) {
    state.exclusiveRights = [];
    stopExclusiveBoardTimer();
    const card = document.getElementById("exclusiveBoardCard");
    const empty = document.getElementById("exclusiveBoardEmpty");
    if (card) card.hidden = true;
    if (empty) {
      empty.hidden = false;
      empty.textContent = `배타적사용권 현황을 불러오지 못했습니다. ${error.message}`;
    }
  }
}

function renderExclusiveBoard() {
  const empty = document.getElementById("exclusiveBoardEmpty");
  const card = document.getElementById("exclusiveBoardCard");
  const items = state.exclusiveRights || [];
  if (!empty || !card) return;
  if (!items.length) {
    empty.hidden = false;
    card.hidden = true;
    return;
  }
  empty.hidden = true;
  card.hidden = false;
  renderExclusiveItem();
}

function renderExclusiveItem() {
  const items = state.exclusiveRights || [];
  if (!items.length) return;
  const item = items[state.exclusiveIndex % items.length];
  document.getElementById("exclusiveInsuranceType").textContent = item.insurance_type || "unknown";
  document.getElementById("exclusiveCompany").textContent = item.company_name || "-";
  document.getElementById("exclusiveMonths").textContent = item.exclusivity_months ? `${item.exclusivity_months}개월` : "-";
  document.getElementById("exclusiveSubjectName").textContent = item.subject_name || "-";
  document.getElementById("exclusiveSummary").textContent = item.summary || item.article_title || "";
  document.getElementById("exclusiveFooter").textContent = [item.acquired_year_month, item.article_title].filter(Boolean).join(" · ");
  document.getElementById("exclusivePager").textContent = `${state.exclusiveIndex + 1} / ${items.length}`;

  const card = document.getElementById("exclusiveBoardCard");
  renderNewsboardLogo(card, "exclusiveCompanyLogo", "exclusiveLogoWrap", item.company_logo_url, item.company_name);
  if (item.article_url) {
    card.href = item.article_url;
    card.classList.remove("disabled");
    card.setAttribute("aria-label", `${item.subject_name || "배타적사용권"} 원문 기사 열기`);
  } else {
    card.removeAttribute("href");
    card.classList.add("disabled");
    card.setAttribute("aria-label", `${item.subject_name || "배타적사용권"} 원문 기사 URL 없음`);
  }
}

function nextExclusiveItem() {
  if (!state.exclusiveRights.length) return;
  state.exclusiveIndex = (state.exclusiveIndex + 1) % state.exclusiveRights.length;
  renderExclusiveItem();
}

function prevExclusiveItem() {
  if (!state.exclusiveRights.length) return;
  state.exclusiveIndex = (state.exclusiveIndex - 1 + state.exclusiveRights.length) % state.exclusiveRights.length;
  renderExclusiveItem();
}

function startExclusiveBoardTimer() {
  stopExclusiveBoardTimer();
  if ((state.exclusiveRights || []).length <= 1) return;
  state.exclusiveTimer = setInterval(nextExclusiveItem, 5000);
}

function stopExclusiveBoardTimer() {
  if (state.exclusiveTimer) {
    clearInterval(state.exclusiveTimer);
    state.exclusiveTimer = null;
  }
}

function restoreSingleSelection(id, value) {
  if (!value) return;
  const select = document.getElementById(id);
  if (Array.from(select.options).some((option) => option.value === value)) {
    select.value = value;
  }
}

function fillReleaseYearCheckboxes(selectedYears = new Set(), { selectAllWhenEmpty = false } = {}) {
  const years = (state.options?.years || []).filter((year) => year !== "전체");
  fillCheckboxList("releaseYearOptions", years.map((year) => ({ value: year, label: year })), selectedYears, { selectAllWhenEmpty });
  syncSelectAllButton("releaseYearAll", "releaseYearOptions");
  fillMobileReleaseYearCheckboxes(selectedYears, { selectAllWhenEmpty });
  updateMobileFilterSummary();
}

function fillCompanyCheckboxes(selectedCompanies = new Set(), { selectAllWhenEmpty = false } = {}) {
  const selectedInsuranceType = document.getElementById("insuranceType").value;
  const companyFilter = document.getElementById("companyFilter");
  const allButton = document.getElementById("companyNamesAll");
  if (!selectedInsuranceType) {
    companyFilter.classList.add("disabled");
    allButton.disabled = true;
    document.getElementById("companyNames").innerHTML = '<div class="checkbox-empty">업종을 먼저 선택하세요.</div>';
    syncSelectAllButton("companyNamesAll", "companyNames");
    fillMobileCompanyCheckboxes(selectedCompanies, { selectAllWhenEmpty });
    updateMobileFilterSummary();
    return;
  }

  companyFilter.classList.remove("disabled");
  allButton.disabled = false;
  const companies = (state.options?.companies || []).filter((item) => item.insurance_type === selectedInsuranceType);
  fillCheckboxList(
    "companyNames",
    companies.map((item) => ({
      value: item.company_name,
      label: item.display_label || item.company_name,
      title: [
        item.insurance_type,
        item.establishment_year ? `설립년도: ${item.establishment_year}` : null,
        item.establishment_source_note,
        item.company_role,
        item.status_2024_2026,
      ].filter(Boolean).join(" / "),
    })),
    selectedCompanies,
    { selectAllWhenEmpty },
  );
  syncSelectAllButton("companyNamesAll", "companyNames");
  fillMobileCompanyCheckboxes(selectedCompanies, { selectAllWhenEmpty });
  updateMobileFilterSummary();
}

function fillProductTypeCheckboxes(selectedProductTypes = new Set(), { selectAllWhenEmpty = false } = {}) {
  const items = (state.options?.product_types || []).map((item) => ({ value: item.code, label: item.name }));
  fillCheckboxList("productTypeCodes", items, selectedProductTypes, { selectAllWhenEmpty });
  syncSelectAllButton("productTypeCodesAll", "productTypeCodes");
  fillMobileProductTypeCheckboxes(selectedProductTypes, { selectAllWhenEmpty });
  updateMobileFilterSummary();
}

function initExclusiveRightListFilters() {
  syncExclusiveRightListInsuranceType();
  fillExclusiveRightCompanyCheckboxes(new Set(), { selectAllWhenEmpty: true });
}

function syncExclusiveRightListInsuranceType() {
  const source = document.getElementById("insuranceType");
  const target = document.getElementById("exclusiveRightInsuranceType");
  if (!source || !target || state.exclusiveRightListUserTouched) return;
  target.value = source.value || "";
  fillExclusiveRightCompanyCheckboxes(new Set(), { selectAllWhenEmpty: true });
}

function fillExclusiveRightCompanyCheckboxes(selectedValues = new Set(), { selectAllWhenEmpty = false } = {}) {
  const selectedInsuranceType = document.getElementById("exclusiveRightInsuranceType")?.value || "";
  const companies = (state.options?.companies || []).filter((item) => !selectedInsuranceType || item.insurance_type === selectedInsuranceType);
  fillCheckboxList(
    "exclusiveRightCompanyNames",
    companies.map((item) => ({
      value: item.company_name,
      label: item.display_label || item.company_name,
      title: [item.company_name, item.establishment_year ? `설립년도: ${item.establishment_year}` : null].filter(Boolean).join(" / "),
    })),
    selectedValues,
    { selectAllWhenEmpty }
  );
  syncSelectAllButton("exclusiveRightCompanyNamesAll", "exclusiveRightCompanyNames");
  fillMobileExclusiveCompanyCheckboxes(selectedValues, { selectAllWhenEmpty });
  updateMobileExclusiveFilterSummary();
}

function collectExclusiveRightQuery({ forExport = false } = {}) {
  const payload = {
    insurance_type: document.getElementById("exclusiveRightInsuranceType")?.value || null,
    company_names: selectedFilterValues("exclusiveRightCompanyNames"),
    include_review: false,
    keyword: document.getElementById("exclusiveRightKeyword")?.value.trim() || null,
  };
  const preset = document.getElementById("exclusiveRightPeriodPreset")?.value || "12m";
  if (preset === "12m") {
    payload.months_back = 12;
  } else if (preset === "custom") {
    payload.acquired_year_month_from = document.getElementById("exclusiveRightMonthFrom")?.value || null;
    payload.acquired_year_month_to = document.getElementById("exclusiveRightMonthTo")?.value || null;
  }
  if (!forExport) {
    payload.limit = 200;
  }
  Object.keys(payload).forEach((key) => {
    if (payload[key] === null || payload[key] === "" || (Array.isArray(payload[key]) && !payload[key].length)) delete payload[key];
  });
  return payload;
}

async function loadExclusiveRightList() {
  const table = document.getElementById("exclusiveRightListTable");
  if (!table) return;
  const message = document.getElementById("exclusiveRightListMessage");
  try {
    const params = new URLSearchParams();
    const query = collectExclusiveRightQuery();
    Object.entries(query).forEach(([key, value]) => params.set(key, String(value)));
    const result = await getJson(`/api/exclusive-rights?${params.toString()}`);
    state.exclusiveRightList = result.items || [];
    state.exclusiveRightListLoaded = true;
    renderExclusiveRightList(state.exclusiveRightList);
    document.getElementById("exclusiveRightListMeta").textContent = `${state.exclusiveRightList.length}건`;
    if (message) message.textContent = state.exclusiveRightList.length ? "" : "조건에 해당하는 배타적사용권 내역이 없습니다.";
  } catch (error) {
    state.exclusiveRightList = [];
    state.exclusiveRightListLoaded = false;
    renderMobileExclusiveCards([]);
    renderTable(table, [], { emptyText: error.message });
    if (message) message.textContent = error.message;
  }
}

function renderExclusiveRightList(items) {
  const table = document.getElementById("exclusiveRightListTable");
  renderMobileExclusiveCards(items || []);
  const rows = (items || []).map((item) => ({
    item,
    insurance_type: item.insurance_type,
    company_name: item.company_name,
    subject_name: item.subject_name,
    exclusivity_months: item.exclusivity_months ? `${item.exclusivity_months}개월` : "-",
    acquired_year_month: item.acquired_year_month,
    feature_summary: item.feature_summary,
    primary_article_title: item.primary_article_title || item.article_title,
  }));
  renderTable(table, rows, {
    emptyText: "조건에 해당하는 배타적사용권 내역이 없습니다.",
    preferredKeys: [
      "insurance_type",
      "company_name",
      "subject_name",
      "exclusivity_months",
      "acquired_year_month",
      "feature_summary",
      "primary_article_title",
    ],
    cellRenderer: (key, value, row) => {
      if (key === "primary_article_title" && row.item.primary_article_url) {
        const link = document.createElement("a");
        link.href = row.item.primary_article_url;
        link.target = "_blank";
        link.rel = "noreferrer";
        link.textContent = value || "원문 기사";
        return link;
      }
      return document.createTextNode(display(value));
    },
  });
}

async function downloadExclusiveRightsExcel() {
  const button = document.getElementById("exclusiveRightExcelDownload");
  if (button) button.disabled = true;
  try {
    const response = await fetch("/api/exclusive-rights/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collectExclusiveRightQuery({ forExport: true })),
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `요청 실패: ${response.status}`);
    }
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="?([^"]+)"?/i);
    triggerDownload(blob, match?.[1] || "exclusive_rights.xlsx");
  } catch (error) {
    const message = document.getElementById("exclusiveRightListMessage");
    if (message) message.textContent = error.message;
  } finally {
    if (button) button.disabled = false;
  }
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function fillCheckboxList(id, items, selectedValuesSet = new Set(), { selectAllWhenEmpty = false } = {}) {
  const list = document.getElementById(id);
  list.innerHTML = "";
  const shouldSelectAll = selectAllWhenEmpty && selectedValuesSet.size === 0;
  for (const item of items) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = item.value;
    input.checked = shouldSelectAll || selectedValuesSet.has(item.value);
    const span = document.createElement("span");
    span.textContent = item.label;
    if (item.title) label.title = item.title;
    label.appendChild(input);
    label.appendChild(span);
    list.appendChild(label);
  }
  if (!items.length) {
    list.innerHTML = '<div class="checkbox-empty">선택 가능한 항목이 없습니다.</div>';
  }
}

function syncSelectAllButton(allId, listId) {
  const allButton = document.getElementById(allId);
  const list = document.getElementById(listId);
  const hasItems = Boolean(list.querySelector("input[type='checkbox']"));
  const isAllSelected = hasItems && allItemsSelected(listId);
  allButton.classList.toggle("active", isAllSelected);
  allButton.setAttribute("aria-pressed", isAllSelected ? "true" : "false");
  allButton.textContent = isAllSelected ? "전체해제" : "전체선택";
}

function setAllCheckboxes(listId, checked) {
  document.querySelectorAll(`#${listId} input[type='checkbox']`).forEach((input) => {
    input.checked = checked;
  });
}

function allItemsSelected(listId) {
  const inputs = Array.from(document.querySelectorAll(`#${listId} input[type='checkbox']`));
  return inputs.length > 0 && inputs.every((input) => input.checked);
}

function selectedCheckboxValues(id) {
  return Array.from(document.querySelectorAll(`#${id} input[type='checkbox']:checked`)).map((input) => input.value);
}

function selectedFilterValues(id) {
  const inputs = Array.from(document.querySelectorAll(`#${id} input[type='checkbox']`));
  if (!inputs.length) return [];
  const values = inputs.filter((input) => input.checked).map((input) => input.value);
  if (values.length === inputs.length) return [];
  return values;
}

function optionLabelsForValues(options, values, valueKey = "value", labelKey = "label") {
  if (!values.length) return [];
  const labelMap = new Map((options || []).map((item) => [item[valueKey], item[labelKey] || item[valueKey]]));
  return values.map((value) => labelMap.get(value) || value);
}

function compactFilterLabel(labels, fallback) {
  if (!labels.length) return fallback;
  if (labels.length <= 2) return labels.join(", ");
  return `${labels.slice(0, 2).join(", ")} 외 ${labels.length - 2}`;
}

function optionFlags() {
  return {
    include_changed_companies: true,
    include_short_term_insurers: true,
  };
}

function currentQuery() {
  const years = selectedFilterValues("releaseYearOptions");
  const selectedInsuranceType = document.getElementById("insuranceType").value;
  const keyword = document.getElementById("keywordInput")?.value.trim() || null;
  const flags = optionFlags();
  const productTypeCodes = selectedFilterValues("productTypeCodes");
  return {
    release_year: years.length === 1 ? years[0] : "전체",
    release_years: years,
    release_month: "전체",
    insurance_type: selectedInsuranceType || "전체",
    company_names: selectedInsuranceType ? selectedFilterValues("companyNames") : [],
    product_type_codes: productTypeCodes,
    classification_mode: "primary_only",
    pivot_preset: "custom",
    custom_rows: ["company_name", "product_type_name"],
    custom_columns: [],
    custom_metrics: ["product_count", "article_count"],
    include_review: true,
    min_confidence: 0,
    include_excluded_policy_products: false,
    keyword,
    keyword_fields: [
      "product_name",
      "raw_product_name",
      "product_alias",
      "product_summary",
      "coverage_summary",
      "coverage_name",
      "article_title",
      "article_description",
    ],
    ...flags,
  };
}

async function runQuery() {
  const shell = document.querySelector(".dashboard-shell");
  shell.classList.add("loading");
  try {
    const query = currentQuery();
    state.lastQuery = query;
    state.selectedProductId = null;
    const result = await postJson("/api/dashboard/query", query);
    state.products = result.products || [];
    renderProducts(state.products);
  } catch (error) {
    renderError(error);
  } finally {
    shell.classList.remove("loading");
  }
}

async function downloadExcel() {
  const button = document.getElementById("downloadExcel");
  button.disabled = true;
  setButtonLabel(button, "다운로드 준비 중");
  try {
    const response = await fetch("/api/dashboard/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(currentQuery()),
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `요청 실패: ${response.status}`);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "insurance_product_comparison.xlsx";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  } catch (error) {
    renderError(error);
  } finally {
    button.disabled = false;
    setButtonLabel(button, "엑셀 다운로드");
  }
}

function renderProducts(products) {
  document.getElementById("productMeta").textContent = `${products.length}개 상품`;
  renderMobileProductCards(products);
  const table = document.getElementById("productTable");
  const rows = products.map((item) => ({
    product: item,
    normalized_product_name: item.normalized_product_name,
    company_name: item.company_name,
    release_year_month: item.release_year_month,
    primary_product_type: item.primary_product_type,
  }));
  renderTable(table, rows, {
    emptyText: "조회된 상품이 없습니다.",
    preferredKeys: [
      "normalized_product_name",
      "company_name",
      "release_year_month",
      "primary_product_type",
    ],
    rowClass: (row) => (row.product.product_id === state.selectedProductId ? "selected-row" : ""),
    cellRenderer: (key, value, row) => {
      if (key === "normalized_product_name") {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `product-link${row.product.product_id === state.selectedProductId ? " selected" : ""}`;
        button.textContent = value || "-";
        button.addEventListener("click", () => loadProductDetail(row.product.product_id));
        return button;
      }
      return document.createTextNode(display(value));
    },
  });
}

function renderTable(table, records, options = {}) {
  const preferred = options.preferredKeys || [];
  table.innerHTML = "";
  if (!records.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.textContent = options.emptyText || "데이터가 없습니다.";
    tr.appendChild(td);
    table.appendChild(tr);
    return;
  }
  const keys = preferred.length ? preferred.filter((key) => key in records[0]) : Object.keys(records[0]);
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  for (const key of keys) {
    const th = document.createElement("th");
    th.textContent = LABELS[key] || key;
    headerRow.appendChild(th);
  }
  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (const row of records) {
    const tr = document.createElement("tr");
    if (options.rowClass) {
      const className = options.rowClass(row);
      if (className) tr.className = className;
    }
    for (const key of keys) {
      const td = document.createElement("td");
      const value = row[key];
      if (options.cellRenderer) {
        td.appendChild(options.cellRenderer(key, value, row));
      } else {
        td.textContent = display(value);
      }
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
}

async function loadProductDetail(productId) {
  state.selectedProductId = productId;
  renderProducts(state.products);
  const detail = document.getElementById("detailContent");
  detail.innerHTML = '<div class="detail-empty">상품 상세를 불러오는 중입니다.</div>';
  try {
    const product = await getJson(`/api/products/${productId}`);
    detail.innerHTML = detailHtml(product);
  } catch (error) {
    detail.innerHTML = `<div class="detail-empty">${escapeHtml(error.message)}</div>`;
  } finally {
    document.querySelector(".detail-panel-full")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function detailHtml(product) {
  const assignments = product.product_type_assignments || [];
  const primary = assignments.find((item) => item.assignment_role === "primary") || assignments.find((item) => item.product_type_code === product.primary_product_type_code) || {};
  const feature = (product.structured_features || [])[0] || {};
  const insight = (product.narrative_insights || [])[0] || {};
  const coverages = dedupeCoverages(product.major_coverages || []);
  const sales = product.sales_metrics || [];
  const articles = product.articles || [];
  return `
    <section class="detail-hero">
      <h3>${escapeHtml(product.normalized_product_name)}</h3>
      ${kv([
        ["보험회사", product.company_name],
        ["출시년월", product.release_year_month],
        ["대표 보종군", primary.product_type_name_ko || product.primary_product_type_code],
      ])}
    </section>
    <div class="detail-grid">
      ${section("상품 기본정보", kv([
        ["상품명", product.normalized_product_name],
        ["보험회사", product.company_name],
        ["출시년월", product.release_year_month],
        ["대표 보종군", primary.product_type_name_ko || product.primary_product_type_code],
      ]), "detail-card")}
      ${section("상품특성 요약", kv([
        ["가입연령", ageText(feature.join_age_min, feature.join_age_max)],
        ["고지유형", feature.notification_type],
        ["판매채널", feature.sales_channel],
        ["갱신/비갱신", feature.renewal_type],
        ["납입기간", feature.payment_period],
        ["보험기간", feature.coverage_period],
        ["상품특징 요약", insight.feature_summary],
        ["상품개발 관점 요약", insight.product_development_summary],
        ["마케팅 요약", insight.marketing_summary],
        ["언더라이팅 요약", insight.underwriting_summary],
      ]), "detail-card")}
    </div>
    ${section("주요보장 리스트", miniTable(coverages, [
      ["coverage_name_normalized", "보장명"],
      ["risk_area", "보장영역"],
      ["benefit_type", "급부유형"],
      ["max_amount_krw", "최대보장금액"],
      ["amount_basis", "금액기준"],
      ["condition_text", "지급조건"],
      ["coverage_summary", "보장요약"],
    ]), "coverage-full-section")}
    ${section("판매실적", miniTable(sales, [
      ["metric_name", "항목"],
      ["metric_value", "값"],
      ["metric_unit", "단위"],
      ["metric_period", "기간"],
      ["metric_basis", "기준"],
    ]))}
    ${section("관련기사", miniTable(articles, [
      ["title", "기사 제목"],
      ["pub_date", "발행일"],
      ["url", "출처 URL"],
      ["original_url", "원문 URL"],
    ], true))}
  `;
}

function section(title, body, className = "") {
  return `<section class="detail-section ${escapeAttribute(className)}"><h3>${escapeHtml(title)}</h3>${body}</section>`;
}

function kv(items) {
  return `<dl class="kv">${items
    .map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(display(value))}</dd>`)
    .join("")}</dl>`;
}

function miniTable(rows, columns, linkUrls = false) {
  if (!rows.length) return '<div class="detail-empty">데이터가 없습니다.</div>';
  return `<div class="table-wrap"><table class="mini-table"><thead><tr>${columns.map(([, label]) => `<th>${escapeHtml(label)}</th>`).join("")}</tr></thead><tbody>${rows
    .map(
      (row) =>
        `<tr>${columns
          .map(([key]) => {
            const value = row[key];
            if (linkUrls && (key === "url" || key === "original_url") && value) {
              return `<td><a href="${escapeAttribute(value)}" target="_blank" rel="noreferrer">열기</a></td>`;
            }
            const rendered = key.includes("confidence") ? formatConfidence(value) : key.includes("amount") || key === "metric_value" ? number(value) : display(value);
            return `<td class="${key === "evidence_text" ? "evidence" : ""}">${escapeHtml(rendered)}</td>`;
          })
          .join("")}</tr>`,
    )
    .join("")}</tbody></table></div>`;
}

function dedupeCoverages(coverages) {
  const bestByKey = new Map();
  const order = [];
  for (const coverage of coverages || []) {
    const key = coverageIdentityKey(coverage);
    if (!bestByKey.has(key)) {
      bestByKey.set(key, coverage);
      order.push(key);
      continue;
    }
    if (coverageSelectionScore(coverage) > coverageSelectionScore(bestByKey.get(key))) {
      bestByKey.set(key, coverage);
    }
  }
  return order.map((key) => bestByKey.get(key));
}

function coverageIdentityKey(coverage) {
  const family = coverageComponentFamily(coverage);
  if (family) {
    return [
      `family:${family}`,
      normalizeCoverageArea(coverage.risk_area),
      normalizeBenefitType(coverage.benefit_type),
      coverage.max_amount_krw || "",
    ].join("|");
  }
  return [
    compactCoverageText(coverage.coverage_name_normalized || coverage.coverage_name_raw || coverage.coverage_summary),
    normalizeCoverageArea(coverage.risk_area),
    normalizeBenefitType(coverage.benefit_type),
    coverage.max_amount_krw || "",
    compactCoverageText(coverage.condition_text || coverage.limit_text),
  ].join("|");
}

function coverageSelectionScore(coverage) {
  const summary = coverage.coverage_summary || "";
  return [
    summary ? 1 : 0,
    String(summary).length,
    coverage.max_amount_krw ? 1 : 0,
    coverage.condition_text ? 1 : 0,
    Number(coverage.confidence || 0),
    -Number(coverage.display_order || 0),
    -Number(coverage.coverage_id || 0),
  ].reduce((score, value) => score * 1000 + value, 0);
}

function compactCoverageText(value) {
  return value == null ? "" : String(value).toLowerCase().replace(/[\W_]+/g, "");
}

function normalizeCoverageArea(value) {
  const compact = compactCoverageText(value);
  if (/(임신|출산|산모)/.test(compact)) return "임신출산";
  if (/(법률|변호사|소송)/.test(compact)) return "법률비용";
  if (/환급/.test(compact)) return "환급";
  return compact;
}

function normalizeBenefitType(value) {
  const compact = compactCoverageText(value);
  if (/(보험금|지원금|축하금)/.test(compact)) return "정액";
  if (/환급금/.test(compact)) return "환급";
  if (/유예/.test(compact)) return "보험료유예";
  return compact;
}

function coverageComponentFamily(coverage) {
  const text = [
    coverage.coverage_name_normalized,
    coverage.coverage_name_raw,
    coverage.risk_area,
    coverage.benefit_type,
    coverage.condition_text,
    coverage.limit_text,
    coverage.coverage_summary,
    coverage.evidence_text,
  ].map((value) => String(value || "")).join(" ");
  if (/(임신\s*지원|임신\s*축하|임신\s*보험료)/.test(text)) return "pregnancy_support";
  if (/(출산\s*지원|출산\s*축하|출산\s*하면|출산\s*보험료)/.test(text)) return "childbirth_support";
  if (/(법률\s*비용|변호사\s*비용|소송\s*비용)/.test(text)) return "legal_cost";
  if (/(보험료\s*환급|특약\s*보험료\s*환급|건강\s*환급)/.test(text)) return "refund_premium";
  return "";
}

function aliasList(aliases) {
  if (!aliases.length) return '<div class="detail-empty">원문 등장명이 아직 기록되지 않았습니다.</div>';
  return `<ul class="alias-list">${aliases
    .map((item) => {
      const count = item.observation_count ? ` (${number(item.observation_count)}회)` : "";
      const candidate = item.normalized_product_name_candidate && item.normalized_product_name_candidate !== item.raw_product_name
        ? ` <span>${escapeHtml(item.normalized_product_name_candidate)}</span>`
        : "";
      return `<li><strong>${escapeHtml(display(item.raw_product_name))}</strong>${candidate}${escapeHtml(count)}</li>`;
    })
    .join("")}</ul>`;
}

function ageText(min, max) {
  if (min == null && max == null) return "-";
  if (min != null && max != null) return `${min}세~${max}세`;
  if (min != null) return `${min}세 이상`;
  return `${max}세 이하`;
}

function isMobileViewport() {
  return window.matchMedia("(max-width: 767px)").matches;
}

function pushMobileOverlayHistory(overlayName) {
  if (!isMobileViewport() || !overlayName || !window.history?.pushState) return;
  if (window.history.state?.mobileOverlay === overlayName) return;
  window.history.pushState({ ...(window.history.state || {}), mobileOverlay: overlayName }, "", window.location.href);
}

function shouldCloseViaHistory(overlayName, options = {}) {
  return !options.fromHistory && isMobileViewport() && window.history.state?.mobileOverlay === overlayName;
}

function currentVisibleMobileOverlay() {
  if (!document.getElementById("mobileProductDetailModal")?.hidden) return state.mobileOverlayNames.productDetail;
  if (!document.getElementById("mobileExclusiveFilterSheet")?.hidden) return state.mobileOverlayNames.exclusiveFilter;
  if (!document.getElementById("mobileFilterSheet")?.hidden) return state.mobileOverlayNames.productFilter;
  return null;
}

function handleMobileOverlayPopState() {
  if (!isMobileViewport()) return;
  closeCurrentMobileOverlay({ fromHistory: true });
}

function closeCurrentMobileOverlay(options = {}) {
  const overlayName = currentVisibleMobileOverlay();
  if (!overlayName) return false;
  if (overlayName === state.mobileOverlayNames.productDetail) {
    closeMobileProductDetail(options);
    return true;
  }
  if (overlayName === state.mobileOverlayNames.exclusiveFilter) {
    closeMobileExclusiveFilterSheet(options);
    return true;
  }
  if (overlayName === state.mobileOverlayNames.productFilter) {
    closeMobileFilterSheet(options);
    return true;
  }
  return false;
}

function initMobileLayout() {
  setActiveMobileView(state.activeMobileView);
  window.addEventListener("popstate", handleMobileOverlayPopState);
  document.querySelectorAll("[data-mobile-view-tab]").forEach((button) => {
    button.addEventListener("click", () => setActiveMobileView(button.dataset.mobileViewTab));
  });

  bindCheckboxGroup("mobileReleaseYearAll", "mobileReleaseYearOptions");
  bindCheckboxGroup("mobileCompanyNamesAll", "mobileCompanyNames");
  bindCheckboxGroup("mobileProductTypeCodesAll", "mobileProductTypeCodes");
  bindCheckboxGroup("mobileExclusiveCompanyNamesAll", "mobileExclusiveCompanyNames");

  ["mobileReleaseYearOptions", "mobileCompanyNames", "mobileProductTypeCodes"].forEach((id) => {
    document.getElementById(id)?.addEventListener("change", updateMobileFilterSummary);
  });
  document.getElementById("mobileCompanySearch")?.addEventListener("input", () => {
    fillMobileCompanyCheckboxes(new Set(selectedCheckboxValues("mobileCompanyNames")), { selectAllWhenEmpty: allItemsSelected("mobileCompanyNames") });
  });
  document.getElementById("mobileKeywordInput")?.addEventListener("input", updateMobileFilterSummary);

  document.querySelectorAll("[data-mobile-insurance]").forEach((button) => {
    button.addEventListener("click", () => {
      setMobileInsuranceType(button.dataset.mobileInsurance || "");
      fillMobileCompanyCheckboxes(new Set(), { selectAllWhenEmpty: true });
      updateMobileFilterSummary();
    });
  });

  document.getElementById("openMobileFilter")?.addEventListener("click", () => openMobileFilterSheet("product"));
  document.getElementById("closeMobileFilter")?.addEventListener("click", closeMobileFilterSheet);
  document.querySelector("[data-mobile-filter-close]")?.addEventListener("click", closeMobileFilterSheet);
  document.getElementById("resetMobileFilter")?.addEventListener("click", resetMobileProductFilter);
  document.getElementById("applyMobileFilter")?.addEventListener("click", applyMobileProductFilter);

  document.querySelectorAll("[data-mobile-exclusive-insurance]").forEach((button) => {
    button.addEventListener("click", () => {
      setMobileExclusiveInsuranceType(button.dataset.mobileExclusiveInsurance || "");
      fillMobileExclusiveCompanyCheckboxes(new Set(), { selectAllWhenEmpty: true });
      updateMobileExclusiveFilterSummary();
    });
  });
  document.getElementById("mobileExclusiveCompanySearch")?.addEventListener("input", () => {
    fillMobileExclusiveCompanyCheckboxes(new Set(selectedCheckboxValues("mobileExclusiveCompanyNames")), {
      selectAllWhenEmpty: allItemsSelected("mobileExclusiveCompanyNames"),
    });
  });
  ["mobileExclusiveCompanyNames", "mobileExclusivePeriodPreset", "mobileExclusiveMonthFrom", "mobileExclusiveMonthTo", "mobileExclusiveKeyword"].forEach((id) => {
    document.getElementById(id)?.addEventListener("change", updateMobileExclusiveFilterSummary);
    document.getElementById(id)?.addEventListener("input", updateMobileExclusiveFilterSummary);
  });
  document.getElementById("openMobileExclusiveFilter")?.addEventListener("click", () => openMobileFilterSheet("exclusive"));
  document.getElementById("closeMobileExclusiveFilter")?.addEventListener("click", closeMobileExclusiveFilterSheet);
  document.querySelector("[data-mobile-exclusive-filter-close]")?.addEventListener("click", closeMobileExclusiveFilterSheet);
  document.getElementById("resetMobileExclusiveFilter")?.addEventListener("click", resetMobileExclusiveFilter);
  document.getElementById("applyMobileExclusiveFilter")?.addEventListener("click", applyMobileExclusiveFilter);

  document.getElementById("closeMobileProductDetail")?.addEventListener("click", closeMobileProductDetail);
  document.querySelector("[data-mobile-detail-close]")?.addEventListener("click", closeMobileProductDetail);

  document.querySelectorAll(".mobile-filter-section-title").forEach((button) => {
    button.addEventListener("click", () => {
      const expanded = button.getAttribute("aria-expanded") !== "false";
      button.setAttribute("aria-expanded", expanded ? "false" : "true");
      button.closest(".mobile-filter-section")?.classList.toggle("collapsed", expanded);
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (closeCurrentMobileOverlay()) return;
    closeMobileFilterSheet();
    closeMobileExclusiveFilterSheet();
    closeMobileProductDetail();
  });
}

async function setActiveMobileView(view) {
  const normalized = view === "exclusive-rights" ? "exclusive-rights" : "products";
  state.activeMobileView = normalized;
  document.querySelector(".dashboard-shell")?.setAttribute("data-mobile-active-view", normalized);
  document.querySelectorAll("[data-mobile-view-tab]").forEach((button) => {
    const active = button.dataset.mobileViewTab === normalized;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
  closeMobileFilterSheet({ fromHistory: true });
  closeMobileExclusiveFilterSheet({ fromHistory: true });
  if (normalized === "exclusive-rights") {
    closeMobileProductDetail({ fromHistory: true });
    stopMonthlyBoardTimer();
    startExclusiveBoardTimer();
    if (!state.exclusiveRightListLoaded) {
      await loadExclusiveRightList();
    } else {
      renderExclusiveRightList(state.exclusiveRightList || []);
      updateMobileExclusiveFilterSummary();
    }
  } else {
    stopExclusiveBoardTimer();
    startMonthlyBoardTimer();
    renderMobileProductCards(state.products || []);
    updateMobileFilterSummary();
  }
}

function setMobileInsuranceType(value) {
  document.querySelectorAll("[data-mobile-insurance]").forEach((button) => {
    const active = (button.dataset.mobileInsurance || "") === (value || "");
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
  document.getElementById("mobileInsuranceTypeSummary").textContent = value || "전체";
}

function getMobileInsuranceType() {
  return document.querySelector("[data-mobile-insurance].active")?.dataset.mobileInsurance || "";
}

function setMobileExclusiveInsuranceType(value) {
  document.querySelectorAll("[data-mobile-exclusive-insurance]").forEach((button) => {
    const active = (button.dataset.mobileExclusiveInsurance || "") === (value || "");
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
  document.getElementById("mobileExclusiveInsuranceSummary").textContent = value || "전체";
}

function getMobileExclusiveInsuranceType() {
  return document.querySelector("[data-mobile-exclusive-insurance].active")?.dataset.mobileExclusiveInsurance || "";
}

function fillMobileReleaseYearCheckboxes(selectedYears = new Set(), { selectAllWhenEmpty = false } = {}) {
  const list = document.getElementById("mobileReleaseYearOptions");
  if (!list) return;
  const years = (state.options?.years || []).filter((year) => year !== "전체");
  fillCheckboxList("mobileReleaseYearOptions", years.map((year) => ({ value: year, label: year })), selectedYears, { selectAllWhenEmpty });
  syncSelectAllButton("mobileReleaseYearAll", "mobileReleaseYearOptions");
}

function fillMobileCompanyCheckboxes(selectedCompanies = new Set(), { selectAllWhenEmpty = false } = {}) {
  const list = document.getElementById("mobileCompanyNames");
  if (!list) return;
  const selectedInsuranceType = getMobileInsuranceType();
  const search = (document.getElementById("mobileCompanySearch")?.value || "").trim().toLowerCase();
  let companies = (state.options?.companies || []).filter((item) => !selectedInsuranceType || item.insurance_type === selectedInsuranceType);
  if (search) {
    companies = companies.filter((item) => `${item.company_name} ${item.display_label || ""}`.toLowerCase().includes(search));
  }
  fillCheckboxList(
    "mobileCompanyNames",
    companies.map((item) => ({ value: item.company_name, label: item.display_label || item.company_name })),
    selectedCompanies,
    { selectAllWhenEmpty },
  );
  syncSelectAllButton("mobileCompanyNamesAll", "mobileCompanyNames");
}

function fillMobileProductTypeCheckboxes(selectedProductTypes = new Set(), { selectAllWhenEmpty = false } = {}) {
  const list = document.getElementById("mobileProductTypeCodes");
  if (!list) return;
  const items = (state.options?.product_types || []).map((item) => ({ value: item.code, label: item.name }));
  fillCheckboxList("mobileProductTypeCodes", items, selectedProductTypes, { selectAllWhenEmpty });
  syncSelectAllButton("mobileProductTypeCodesAll", "mobileProductTypeCodes");
}

function fillMobileExclusiveCompanyCheckboxes(selectedValues = new Set(), { selectAllWhenEmpty = false } = {}) {
  const list = document.getElementById("mobileExclusiveCompanyNames");
  if (!list) return;
  const selectedInsuranceType = getMobileExclusiveInsuranceType();
  const search = (document.getElementById("mobileExclusiveCompanySearch")?.value || "").trim().toLowerCase();
  let companies = (state.options?.companies || []).filter((item) => !selectedInsuranceType || item.insurance_type === selectedInsuranceType);
  if (search) {
    companies = companies.filter((item) => `${item.company_name} ${item.display_label || ""}`.toLowerCase().includes(search));
  }
  fillCheckboxList(
    "mobileExclusiveCompanyNames",
    companies.map((item) => ({ value: item.company_name, label: item.display_label || item.company_name })),
    selectedValues,
    { selectAllWhenEmpty },
  );
  syncSelectAllButton("mobileExclusiveCompanyNamesAll", "mobileExclusiveCompanyNames");
}

function syncDesktopFiltersToMobile() {
  setMobileInsuranceType(document.getElementById("insuranceType")?.value || "");
  fillMobileReleaseYearCheckboxes(new Set(selectedCheckboxValues("releaseYearOptions")), { selectAllWhenEmpty: allItemsSelected("releaseYearOptions") });
  fillMobileCompanyCheckboxes(new Set(selectedCheckboxValues("companyNames")), { selectAllWhenEmpty: allItemsSelected("companyNames") });
  fillMobileProductTypeCheckboxes(new Set(selectedCheckboxValues("productTypeCodes")), { selectAllWhenEmpty: allItemsSelected("productTypeCodes") });
  const keyword = document.getElementById("keywordInput")?.value || "";
  const mobileKeyword = document.getElementById("mobileKeywordInput");
  if (mobileKeyword) mobileKeyword.value = keyword;
  updateMobileFilterSummary();
}

function syncMobileFiltersToDesktop() {
  const insuranceType = getMobileInsuranceType();
  document.getElementById("insuranceType").value = insuranceType;
  fillReleaseYearCheckboxes(new Set(selectedCheckboxValues("mobileReleaseYearOptions")), { selectAllWhenEmpty: allItemsSelected("mobileReleaseYearOptions") });
  fillCompanyCheckboxes(new Set(selectedCheckboxValues("mobileCompanyNames")), { selectAllWhenEmpty: allItemsSelected("mobileCompanyNames") });
  fillProductTypeCheckboxes(new Set(selectedCheckboxValues("mobileProductTypeCodes")), { selectAllWhenEmpty: allItemsSelected("mobileProductTypeCodes") });
  const keyword = document.getElementById("mobileKeywordInput")?.value || "";
  const desktopKeyword = document.getElementById("keywordInput");
  if (desktopKeyword) desktopKeyword.value = keyword;
  updateMobileFilterSummary();
}

function syncDesktopExclusiveFiltersToMobile() {
  setMobileExclusiveInsuranceType(document.getElementById("exclusiveRightInsuranceType")?.value || "");
  fillMobileExclusiveCompanyCheckboxes(new Set(selectedCheckboxValues("exclusiveRightCompanyNames")), {
    selectAllWhenEmpty: allItemsSelected("exclusiveRightCompanyNames"),
  });
  copyInputValue("exclusiveRightPeriodPreset", "mobileExclusivePeriodPreset");
  copyInputValue("exclusiveRightMonthFrom", "mobileExclusiveMonthFrom");
  copyInputValue("exclusiveRightMonthTo", "mobileExclusiveMonthTo");
  copyInputValue("exclusiveRightKeyword", "mobileExclusiveKeyword");
  updateMobileExclusiveFilterSummary();
}

function syncMobileExclusiveFiltersToDesktop() {
  document.getElementById("exclusiveRightInsuranceType").value = getMobileExclusiveInsuranceType();
  fillExclusiveRightCompanyCheckboxes(new Set(selectedCheckboxValues("mobileExclusiveCompanyNames")), {
    selectAllWhenEmpty: allItemsSelected("mobileExclusiveCompanyNames"),
  });
  copyInputValue("mobileExclusivePeriodPreset", "exclusiveRightPeriodPreset");
  copyInputValue("mobileExclusiveMonthFrom", "exclusiveRightMonthFrom");
  copyInputValue("mobileExclusiveMonthTo", "exclusiveRightMonthTo");
  copyInputValue("mobileExclusiveKeyword", "exclusiveRightKeyword");
  updateMobileExclusiveFilterSummary();
}

function copyInputValue(fromId, toId) {
  const source = document.getElementById(fromId);
  const target = document.getElementById(toId);
  if (source && target) target.value = source.value;
}

function updateMobileFilterSummary() {
  const summary = document.getElementById("mobileFilterSummary");
  if (!summary) return;
  const chips = [];
  const years = selectedFilterValues("mobileReleaseYearOptions");
  const insuranceType = getMobileInsuranceType();
  const companies = selectedFilterValues("mobileCompanyNames");
  const productTypes = selectedFilterValues("mobileProductTypeCodes");
  const productTypeLabels = optionLabelsForValues(state.options?.product_types, productTypes, "code", "name");
  const keyword = document.getElementById("mobileKeywordInput")?.value.trim();
  chips.push(years.length ? `${years.length}개 년도` : "년도 전체");
  chips.push(insuranceType || "업종 전체");
  chips.push(compactFilterLabel(productTypeLabels, "상품군 전체"));
  if (keyword) chips.push(`검색: ${keyword}`);
  summary.textContent = chips.join(" · ");
  document.getElementById("mobileYearCount").textContent = years.length ? `${years.length}개` : "전체";
  document.getElementById("mobileCompanyCount").textContent = companies.length ? `${companies.length}개` : "전체";
  document.getElementById("mobileProductTypeCount").textContent = productTypes.length ? `${productTypes.length}개` : "전체";
}

function updateMobileExclusiveFilterSummary() {
  const summary = document.getElementById("mobileExclusiveFilterSummary");
  if (!summary) return;
  const chips = [];
  const preset = document.getElementById("mobileExclusivePeriodPreset")?.value || "12m";
  const insuranceType = getMobileExclusiveInsuranceType();
  const companies = selectedFilterValues("mobileExclusiveCompanyNames");
  const keyword = document.getElementById("mobileExclusiveKeyword")?.value.trim();
  chips.push(preset === "12m" ? "최근 1년" : preset === "custom" ? "직접 기간" : "전체 기간");
  chips.push(insuranceType || "업종 전체");
  if (keyword) chips.push(`검색: ${keyword}`);
  summary.textContent = chips.join(" · ");
  document.getElementById("mobileExclusiveCompanyCount").textContent = companies.length ? `${companies.length}개` : "전체";
}

function openMobileFilterSheet(type = "product") {
  if (type === "exclusive") {
    updateMobileExclusiveFilterSummary();
    document.getElementById("mobileExclusiveFilterSheet").hidden = false;
    pushMobileOverlayHistory(state.mobileOverlayNames.exclusiveFilter);
  } else {
    syncDesktopFiltersToMobile();
    document.getElementById("mobileFilterSheet").hidden = false;
    pushMobileOverlayHistory(state.mobileOverlayNames.productFilter);
  }
  document.body.classList.add("mobile-scroll-lock");
}

function closeMobileFilterSheet(options = {}) {
  if (shouldCloseViaHistory(state.mobileOverlayNames.productFilter, options)) {
    window.history.back();
    return;
  }
  hideMobileFilterSheet();
}

function hideMobileFilterSheet() {
  const sheet = document.getElementById("mobileFilterSheet");
  if (sheet) sheet.hidden = true;
  if (document.getElementById("mobileExclusiveFilterSheet")?.hidden && document.getElementById("mobileProductDetailModal")?.hidden) {
    document.body.classList.remove("mobile-scroll-lock");
  }
}

function closeMobileExclusiveFilterSheet(options = {}) {
  if (shouldCloseViaHistory(state.mobileOverlayNames.exclusiveFilter, options)) {
    window.history.back();
    return;
  }
  hideMobileExclusiveFilterSheet();
}

function hideMobileExclusiveFilterSheet() {
  const sheet = document.getElementById("mobileExclusiveFilterSheet");
  if (sheet) sheet.hidden = true;
  if (document.getElementById("mobileFilterSheet")?.hidden && document.getElementById("mobileProductDetailModal")?.hidden) {
    document.body.classList.remove("mobile-scroll-lock");
  }
}

function resetMobileProductFilter() {
  setMobileInsuranceType("");
  fillMobileReleaseYearCheckboxes(new Set(), { selectAllWhenEmpty: true });
  fillMobileCompanyCheckboxes(new Set(), { selectAllWhenEmpty: true });
  fillMobileProductTypeCheckboxes(new Set(), { selectAllWhenEmpty: true });
  const keyword = document.getElementById("mobileKeywordInput");
  if (keyword) keyword.value = "";
  updateMobileFilterSummary();
}

async function applyMobileProductFilter() {
  syncMobileFiltersToDesktop();
  closeMobileFilterSheet();
  await loadMonthlyNewProducts();
  if (!isMobileViewport()) await loadRecentExclusiveRights();
  await runQuery();
}

function resetMobileExclusiveFilter() {
  setMobileExclusiveInsuranceType("");
  fillMobileExclusiveCompanyCheckboxes(new Set(), { selectAllWhenEmpty: true });
  ["mobileExclusiveMonthFrom", "mobileExclusiveMonthTo", "mobileExclusiveKeyword"].forEach((id) => {
    const input = document.getElementById(id);
    if (input) input.value = "";
  });
  const preset = document.getElementById("mobileExclusivePeriodPreset");
  if (preset) preset.value = "12m";
  updateMobileExclusiveFilterSummary();
}

async function applyMobileExclusiveFilter() {
  syncMobileExclusiveFiltersToDesktop();
  state.exclusiveRightListUserTouched = true;
  closeMobileExclusiveFilterSheet();
  await loadExclusiveRightList();
}

function renderMobileProductCards(products) {
  const container = document.getElementById("mobileProductCards");
  if (!container) return;
  if (!products.length) {
    container.innerHTML = '<div class="mobile-empty-card">조회된 상품이 없습니다.</div>';
    return;
  }
  container.innerHTML = products.map((item) => {
    const summary = item.product_summary || item.feature_summary || item.coverage_summary || item.summary || "";
    return `
      <article class="mobile-product-card">
        <div class="mobile-card-meta">
          <span>${escapeHtml(display(item.company_name))}</span>
          <span>${escapeHtml(display(item.release_year_month))}</span>
          <span>${escapeHtml(display(item.primary_product_type))}</span>
        </div>
        <h3>${escapeHtml(display(item.normalized_product_name))}</h3>
        <p>${escapeHtml(display(summary))}</p>
        <div class="mobile-card-actions">
          <button type="button" data-mobile-product-id="${escapeAttribute(item.product_id)}">상세보기</button>
        </div>
      </article>
    `;
  }).join("");
  container.querySelectorAll("[data-mobile-product-id]").forEach((button) => {
    button.addEventListener("click", () => openMobileProductDetail(button.dataset.mobileProductId));
  });
}

async function openMobileProductDetail(productId) {
  state.selectedProductId = Number(productId);
  renderProducts(state.products);
  const modal = document.getElementById("mobileProductDetailModal");
  const content = document.getElementById("mobileProductDetailContent");
  if (!modal || !content) return;
  modal.hidden = false;
  document.body.classList.add("mobile-scroll-lock");
  pushMobileOverlayHistory(state.mobileOverlayNames.productDetail);
  content.innerHTML = '<div class="detail-empty">상품 상세를 불러오는 중입니다.</div>';
  try {
    const product = await getJson(`/api/products/${productId}`);
    content.innerHTML = renderMobileProductDetail(product);
  } catch (error) {
    content.innerHTML = `<div class="detail-empty">${escapeHtml(error.message)}</div>`;
  }
}

function closeMobileProductDetail(options = {}) {
  if (shouldCloseViaHistory(state.mobileOverlayNames.productDetail, options)) {
    window.history.back();
    return;
  }
  hideMobileProductDetail();
}

function hideMobileProductDetail() {
  const modal = document.getElementById("mobileProductDetailModal");
  if (modal) modal.hidden = true;
  if (document.getElementById("mobileFilterSheet")?.hidden && document.getElementById("mobileExclusiveFilterSheet")?.hidden) {
    document.body.classList.remove("mobile-scroll-lock");
  }
}

function renderMobileProductDetail(product) {
  const assignments = product.product_type_assignments || [];
  const primary = assignments.find((item) => item.assignment_role === "primary") || assignments.find((item) => item.product_type_code === product.primary_product_type_code) || {};
  const feature = (product.structured_features || [])[0] || {};
  const insight = (product.narrative_insights || [])[0] || {};
  const articles = product.articles || [];
  return `
    <article class="mobile-detail-card">
      <div class="mobile-card-meta">
        <span>${escapeHtml(display(product.company_name))}</span>
        <span>${escapeHtml(display(product.release_year_month))}</span>
        <span>${escapeHtml(display(primary.product_type_name_ko || product.primary_product_type_code))}</span>
      </div>
      <h3>${escapeHtml(display(product.normalized_product_name))}</h3>
      ${mobileDefinitionList([
        ["보험회사", product.company_name],
        ["출시년월", product.release_year_month],
        ["대표 상품군", primary.product_type_name_ko || product.primary_product_type_code],
        ["가입연령", ageText(feature.join_age_min, feature.join_age_max)],
        ["고지유형", feature.notification_type],
        ["판매채널", feature.sales_channel],
      ])}
    </article>
    <section class="mobile-detail-card">
      <h3>요약</h3>
      ${mobileDefinitionList([
        ["상품특징", insight.feature_summary],
        ["상품개발 관점", insight.product_development_summary],
        ["마케팅", insight.marketing_summary],
        ["언더라이팅", insight.underwriting_summary],
      ])}
    </section>
    <section class="mobile-detail-card">
      <h3>주요보장</h3>
      ${renderMobileCoverageCards(product.major_coverages || [])}
    </section>
    <section class="mobile-detail-card">
      <h3>관련기사</h3>
      ${renderMobileArticleLinks(articles)}
    </section>
  `;
}

function mobileDefinitionList(items) {
  return `<dl class="mobile-definition-list">${items
    .filter(([, value]) => value != null && value !== "")
    .map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(display(value))}</dd>`)
    .join("")}</dl>`;
}

function renderMobileCoverageCards(coverages) {
  coverages = dedupeCoverages(coverages || []);
  if (!coverages.length) return '<div class="mobile-empty-card">주요보장 데이터가 없습니다.</div>';
  return `<div class="mobile-coverage-list">${coverages.map((coverage, index) => `
    <details class="mobile-coverage-card" ${index < 3 ? "open" : ""}>
      <summary>${escapeHtml(display(coverage.coverage_name_normalized || coverage.coverage_name_raw))}</summary>
      ${mobileDefinitionList([
        ["보장영역", coverage.risk_area],
        ["급부유형", coverage.benefit_type],
        ["최대보장금액", coverage.max_amount_krw ? number(coverage.max_amount_krw) : null],
        ["금액기준", coverage.amount_basis],
        ["지급조건", coverage.condition_text],
        ["요약", coverage.coverage_summary],
      ])}
    </details>
  `).join("")}</div>`;
}

function renderMobileArticleLinks(articles) {
  if (!articles.length) return '<div class="mobile-empty-card">관련기사 데이터가 없습니다.</div>';
  return `<div class="mobile-article-list">${articles.map((article) => {
    const url = article.original_url || article.url;
    const title = article.title || "대표 기사 보기";
    return url
      ? `<a href="${escapeAttribute(url)}" target="_blank" rel="noreferrer">${escapeHtml(title)}</a>`
      : `<span>${escapeHtml(title)}</span>`;
  }).join("")}</div>`;
}

function renderMobileExclusiveCards(items) {
  const container = document.getElementById("mobileExclusiveCards");
  if (!container) return;
  if (!items.length) {
    container.innerHTML = '<div class="mobile-empty-card">조건에 해당하는 배타적사용권 내역이 없습니다.</div>';
    return;
  }
  container.innerHTML = items.map((item) => {
    const url = item.primary_article_url || item.article_url;
    return `
      <article class="mobile-exclusive-card">
        <div class="mobile-card-meta">
          <span>${escapeHtml(display(item.company_name))}</span>
          <span>${escapeHtml(item.exclusivity_months ? `${item.exclusivity_months}개월` : "-")}</span>
          <span>${escapeHtml(display(item.acquired_year_month))}</span>
        </div>
        <h3>${escapeHtml(display(item.subject_name))}</h3>
        <p>${escapeHtml(display(item.feature_summary || item.summary || ""))}</p>
        ${url ? `<a class="mobile-card-link" href="${escapeAttribute(url)}" target="_blank" rel="noreferrer">대표 기사 보기</a>` : ""}
      </article>
    `;
  }).join("");
}

function bindAdminEvents() {
  document.getElementById("toggleAdminPanel").addEventListener("click", () => {
    const panel = document.getElementById("adminPanel");
    panel.hidden = !panel.hidden;
    if (!panel.hidden && state.adminToken) {
      showAdminControls();
      refreshCrawlJobs();
    }
  });
  document.getElementById("adminAuth").addEventListener("click", authenticateAdmin);
  document.getElementById("refreshCrawlJobs").addEventListener("click", refreshCrawlJobs);
  document.getElementById("refreshLlmSavings").addEventListener("click", refreshLlmSavingsSummary);
  document.getElementById("refreshLlmBatchJobs").addEventListener("click", refreshLlmBatchJobs);
  document.getElementById("createLlmBatchJob").addEventListener("click", createLlmBatchJob);
  document.getElementById("refreshLlmGuardSummary")?.addEventListener("click", refreshLlmGuardSummary);
  document.getElementById("refreshProductConsolidation")?.addEventListener("click", refreshProductConsolidation);
  document.getElementById("runProductConsolidation")?.addEventListener("click", runProductConsolidation);
  document.getElementById("runExclusiveRightExtraction")?.addEventListener("click", runExclusiveRightExtraction);
  document.getElementById("refreshExclusiveRightQueue")?.addEventListener("click", refreshExclusiveRightQueueStatus);
  document.getElementById("runExclusiveRightConsolidation")?.addEventListener("click", runExclusiveRightConsolidation);
  document.getElementById("runFullQwenReview")?.addEventListener("click", runFullQwenReview);
  document.getElementById("refreshScheduledRefresh")?.addEventListener("click", refreshScheduledRefreshStatus);
  document.getElementById("runTestCrawl").addEventListener("click", () => startCrawlJob("/api/admin/crawl-jobs/test-2026-01", adminCrawlOptions()));
  document.getElementById("runBackfillCrawl").addEventListener("click", () => startCrawlJob("/api/admin/crawl-jobs/backfill-2024-2026-05", adminCrawlOptions()));
  document.getElementById("runIncrementalCrawl").addEventListener("click", () =>
    startCrawlJob("/api/admin/crawl-jobs/incremental", {
      ...adminCrawlOptions(),
      days_back: Number(document.getElementById("incrementalDays").value || 14),
    }),
  );
  document.getElementById("runManualCrawl").addEventListener("click", () =>
    startCrawlJob("/api/admin/crawl-jobs/manual-range", {
      ...adminCrawlOptions(),
      date_from: document.getElementById("manualDateFrom").value,
      date_to: document.getElementById("manualDateTo").value,
    }),
  );
  if (state.adminToken) {
    showAdminControls();
  }
}

async function runExclusiveRightExtraction() {
  const mode = document.getElementById("exclusiveRightExtractionMode")?.value || "enqueue_only";
  const crawlJobId = Number(document.getElementById("exclusiveRightCrawlJobId")?.value || 0) || null;
  const payload = {
    limit: Number(document.getElementById("exclusiveRightExtractionLimit")?.value || 100),
    mode,
    crawl_job_id: crawlJobId,
    date_from: document.getElementById("exclusiveRightDateFrom")?.value || null,
    date_to: document.getElementById("exclusiveRightDateTo")?.value || null,
  };
  const message = document.getElementById("adminJobMessage");
  try {
    const result = await adminPostJson("/api/admin/exclusive-rights/extract-pending", payload);
    message.textContent = `배타적사용권 추출 처리: ${JSON.stringify(result)}`;
    await refreshCrawlJobs();
  } catch (error) {
    message.textContent = error.message;
  }
}

async function refreshExclusiveRightQueueStatus() {
  const message = document.getElementById("adminJobMessage");
  const params = new URLSearchParams();
  const crawlJobId = Number(document.getElementById("exclusiveRightCrawlJobId")?.value || 0) || null;
  const dateFrom = document.getElementById("exclusiveRightDateFrom")?.value;
  const dateTo = document.getElementById("exclusiveRightDateTo")?.value;
  if (crawlJobId) params.set("crawl_job_id", String(crawlJobId));
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  try {
    const result = await adminGetJson(`/api/admin/exclusive-rights/extract-queue-status?${params.toString()}`);
    message.textContent = `exclusive-right queue: ${JSON.stringify(result)}`;
  } catch (error) {
    message.textContent = error.message;
  }
}

async function runExclusiveRightConsolidation() {
  const message = document.getElementById("adminJobMessage");
  const crawlJobId = Number(document.getElementById("exclusiveRightCrawlJobId")?.value || 0) || null;
  const payload = {
    mode: "rule_only_apply",
    crawl_job_id: crawlJobId,
    date_from: document.getElementById("exclusiveRightDateFrom")?.value || null,
    date_to: document.getElementById("exclusiveRightDateTo")?.value || null,
  };
  try {
    const result = await adminPostJson("/api/admin/exclusive-rights/consolidate", payload);
    message.textContent = `exclusive-right consolidation: ${JSON.stringify(result)}`;
    await loadRecentExclusiveRights();
  } catch (error) {
    message.textContent = error.message;
  }
}

function adminCrawlOptions() {
  const extractionMode = document.getElementById("crawlExtractionMode")?.value || "none";
  const includeExclusive = Boolean(document.getElementById("crawlIncludeExclusiveRightPipeline")?.checked);
  const exclusiveLimit = Number(document.getElementById("crawlExclusiveRightLimit")?.value || 0) || null;
  return {
    include_llm_extraction: !["none", "screening_only"].includes(extractionMode),
    extraction_mode: extractionMode,
    include_exclusive_right_pipeline: includeExclusive,
    exclusive_right_pipeline_mode: includeExclusive ? (document.getElementById("crawlExclusiveRightMode")?.value || "batch") : "none",
    exclusive_right_auto_submit_batch: Boolean(document.getElementById("crawlExclusiveRightAutoSubmit")?.checked),
    exclusive_right_auto_consolidate: Boolean(document.getElementById("crawlExclusiveRightAutoConsolidate")?.checked),
    exclusive_right_limit: exclusiveLimit,
    include_reinsurers: document.getElementById("crawlIncludeReinsurers").checked,
    include_foreign_branches: document.getElementById("crawlIncludeForeignBranches").checked,
    pipeline_mode: document.getElementById("crawlPipelineMode")?.value || "crawl_only",
    include_qwen_adjudication: Boolean(document.getElementById("crawlIncludeQwen")?.checked),
    qwen_priority: true,
    run_postprocess: Boolean(document.getElementById("crawlRunPostprocess")?.checked),
    run_consolidation: Boolean(document.getElementById("crawlRunConsolidation")?.checked),
  };
}

async function runFullQwenReview() {
  const message = document.getElementById("fullReviewMessage") || document.getElementById("adminJobMessage");
  const crawlJobId = Number(document.getElementById("fullReviewCrawlJobId")?.value || 0) || null;
  const payload = {
    mode: document.getElementById("fullReviewApply")?.checked ? "apply" : "dry_run",
    review_scope: "all",
    date_from: document.getElementById("fullReviewDateFrom")?.value || null,
    date_to: document.getElementById("fullReviewDateTo")?.value || null,
    crawl_job_id: crawlJobId,
    include_rule_review: true,
    include_qwen: true,
    qwen_priority: true,
    max_products: Number(document.getElementById("fullReviewProductLimit")?.value || 50),
    max_exclusive: Number(document.getElementById("fullReviewExclusiveLimit")?.value || 30),
  };
  message.textContent = "Qwen 검토를 실행하는 중입니다.";
  try {
    const result = await adminPostJson("/api/admin/full-review/qwen", payload);
    message.textContent = `Qwen 검토 완료: #${result.full_review_job_id || "-"}`;
    renderTable(document.getElementById("fullReviewTable"), [result], {
      emptyText: "전체 검토 결과가 없습니다.",
      preferredKeys: [
        "full_review_job_id",
        "status",
        "mode",
        "date_from",
        "date_to",
        "crawl_job_id",
        "article_count",
        "product_candidate_count",
        "exclusive_candidate_count",
        "qwen_processed_count",
        "qwen_provider_called_count",
        "qwen_remaining_count",
        "report_path",
        "error_message",
      ],
    });
  } catch (error) {
    message.textContent = error.message;
  }
}

async function refreshScheduledRefreshStatus() {
  const table = document.getElementById("scheduledRefreshTable");
  if (!table || !state.adminToken) return;
  try {
    const result = await adminGetJson("/api/admin/scheduled-refresh/status");
    renderTable(table, [result], {
      emptyText: "예약 새로고침 상태가 없습니다.",
      preferredKeys: [
        "enabled",
        "timezone",
        "days_of_month",
        "hour",
        "lookback_days",
        "running_job_count",
        "next_run_at",
        "latest_job",
      ],
    });
  } catch (error) {
    const message = document.getElementById("fullReviewMessage") || document.getElementById("adminJobMessage");
    message.textContent = error.message;
  }
}

async function authenticateAdmin() {
  const message = document.getElementById("adminAuthMessage");
  message.textContent = "인증 중";
  try {
    const result = await postJson("/api/admin/auth", { password: document.getElementById("adminPassword").value });
    state.adminToken = result.token;
    sessionStorage.setItem("adminToken", result.token);
    message.textContent = `인증 완료: ${display(result.expires_at)}`;
    showAdminControls();
    await refreshCrawlJobs();
  } catch (error) {
    message.textContent = error.message;
  }
}

function showAdminControls() {
  document.getElementById("adminControls").hidden = false;
  if (!state.adminPollTimer) {
    state.adminPollTimer = setInterval(refreshCrawlJobs, 10000);
  }
}

async function startCrawlJob(url, body) {
  const message = document.getElementById("adminJobMessage");
  message.textContent = "작업을 생성하는 중입니다.";
  try {
    const result = await adminPostJson(url, body);
    message.textContent = `작업 생성 완료: #${result.crawl_job_id}`;
    await refreshCrawlJobs();
  } catch (error) {
    message.textContent = error.message;
  }
}

async function refreshCrawlJobs() {
  if (!state.adminToken || document.getElementById("adminPanel").hidden) return;
  try {
    const jobs = await adminGetJson("/api/admin/crawl-jobs");
    renderCrawlJobs(jobs || []);
    await refreshLlmCostSummary();
    await refreshLlmSavingsSummary();
    await refreshLlmBatchJobs();
    await refreshLlmGuardSummary();
    await refreshProductConsolidation();
    await refreshScheduledRefreshStatus();
  } catch (error) {
    document.getElementById("adminJobMessage").textContent = error.message;
    if (error.message.includes("401")) {
      state.adminToken = null;
      sessionStorage.removeItem("adminToken");
    }
  }
}

async function refreshLlmGuardSummary() {
  const table = document.getElementById("llmGuardSummaryTable");
  if (!table || !state.adminToken) return;
  try {
    const summary = await adminGetJson("/api/admin/llm-execution-guard-summary");
    renderTable(table, [summary], {
      emptyText: "LLM 비용절감 가드 요약이 없습니다.",
      preferredKeys: [
        "article_count",
        "screened_high_count",
        "screened_medium_count",
        "screened_low_count",
        "screened_skip_count",
        "llm_queue_count",
        "batch_eligible_queue_count",
        "cluster_reuse_count",
        "extract_run_count",
        "verify_run_count",
        "product_consolidation_run_count",
        "cached_run_count",
        "cache_hit_rate",
        "low_skip_llm_violation_count",
        "article_level_same_product_llm_violation_count",
        "full_body_prompt_violation_count",
        "verify_only_risky_enabled",
        "snippet_only_enabled",
        "cluster_extraction_enabled",
        "product_consolidation_llm_enabled",
      ],
    });
  } catch (error) {
    const tableBody = table.querySelector("tbody") || table;
    tableBody.textContent = error.message;
  }
}

async function runProductConsolidation() {
  const message = document.getElementById("productConsolidationMessage");
  if (!message) return;
  message.textContent = "상품통합 작업을 실행하는 중입니다.";
  try {
    const payload = {
      mode: document.getElementById("productConsolidationMode").value,
      target: document.getElementById("productConsolidationTarget").value,
      limit: Number(document.getElementById("productConsolidationLimit").value || 500),
      use_llm_for_gray_blocks: document.getElementById("productConsolidationUseLlm").checked,
    };
    const result = await adminPostJson("/api/admin/product-consolidation/run", payload);
    message.textContent = `상품통합 완료: #${result.consolidation_job_id}, 자동병합 ${result.auto_merge_count || 0}건`;
    await refreshProductConsolidation(result.consolidation_job_id);
  } catch (error) {
    message.textContent = error.message;
  }
}

async function refreshProductConsolidation(selectedJobId = null) {
  const summaryTable = document.getElementById("productConsolidationSummaryTable");
  const jobTable = document.getElementById("productConsolidationJobTable");
  const blockTable = document.getElementById("productConsolidationBlockTable");
  if (!summaryTable || !jobTable || !state.adminToken) return;
  try {
    const summary = await adminGetJson("/api/admin/product-consolidation/cost-summary");
    renderTable(summaryTable, [summary], {
      emptyText: "상품통합 요약이 없습니다.",
      preferredKeys: [
        "observation_count",
        "block_count",
        "deterministic_auto_merge_count",
        "llm_call_count",
        "review_count",
        "estimated_pairwise_comparison_avoided",
        "estimated_call_reduction_rate",
      ],
    });
    const jobs = await adminGetJson("/api/admin/product-consolidation/jobs");
    renderTable(jobTable, jobs || [], {
      emptyText: "상품통합 작업이 없습니다.",
      preferredKeys: [
        "consolidation_job_id",
        "status",
        "mode",
        "trigger_type",
        "observation_count",
        "provisional_product_count",
        "block_count",
        "auto_merge_count",
        "manual_review_count",
        "llm_call_count",
        "estimated_cost_usd",
        "started_at",
        "finished_at",
        "error_message",
      ],
      cellRenderer: (key, value, row) => {
        if (key === "consolidation_job_id") {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "product-link";
          button.textContent = `#${value}`;
          button.addEventListener("click", () => loadProductConsolidationDetail(row.consolidation_job_id));
          return button;
        }
        return document.createTextNode(display(value));
      },
    });
    if (selectedJobId || (jobs && jobs[0])) {
      await loadProductConsolidationDetail(selectedJobId || jobs[0].consolidation_job_id);
    } else if (blockTable) {
      renderTable(blockTable, [], { emptyText: "상품통합 block이 없습니다." });
    }
  } catch (error) {
    const message = document.getElementById("productConsolidationMessage");
    if (message) message.textContent = error.message;
  }
}

async function loadProductConsolidationDetail(jobId) {
  const table = document.getElementById("productConsolidationBlockTable");
  if (!table || !jobId) return;
  const detail = await adminGetJson(`/api/admin/product-consolidation/jobs/${jobId}`);
  renderTable(table, detail.blocks || [], {
    emptyText: "상품통합 block 상세가 없습니다.",
    preferredKeys: [
      "block_id",
      "status",
      "company_id",
      "partner_company_name",
      "release_month_window",
      "product_type_codes",
      "candidate_product_ids",
      "observation_ids",
      "block_reason",
    ],
  });
}

async function createLlmBatchJob() {
  const message = document.getElementById("llmBatchMessage");
  message.textContent = "Batch 작업을 생성하는 중입니다.";
  try {
    const payload = {
      task_type: document.getElementById("llmBatchTaskType")?.value || "extract",
      provider: "gemini",
      model_name: document.getElementById("llmBatchModel").value || "gemini-2.5-flash",
      limit: Number(document.getElementById("llmBatchLimit").value || 1000),
      submit: document.getElementById("llmBatchSubmitNow").checked,
    };
    const crawlJobId = Number(document.getElementById("llmBatchCrawlJobId")?.value || 0);
    if (crawlJobId > 0) payload.crawl_job_id = crawlJobId;
    const result = await adminPostJson("/api/admin/llm-batch-jobs/create", payload);
    message.textContent = `Batch 생성 완료: #${result.llm_batch_job_id}`;
    await refreshLlmBatchJobs();
  } catch (error) {
    message.textContent = error.message;
  }
}

async function refreshLlmBatchJobs() {
  const table = document.getElementById("llmBatchJobTable");
  if (!table || !state.adminToken) return;
  const taskType = document.getElementById("llmBatchTaskType")?.value || "extract";
  const payload = await adminGetJson(`/api/admin/llm-batch-jobs?task_type=${encodeURIComponent(taskType)}`);
  const message = document.getElementById("llmBatchMessage");
  if (message) {
    message.textContent = `Batch eligible pending queue: ${payload.pending_batch_eligible_count || 0}`;
  }
  renderTable(table, payload.jobs || [], {
    emptyText: "LLM Batch 작업이 없습니다.",
    preferredKeys: [
      "llm_batch_job_id",
      "crawl_job_id",
      "status",
      "provider_status",
      "provider_batch_id",
      "model_name",
      "request_count",
      "completed_count",
      "failed_count",
      "submitted_at",
      "completed_at",
      "error_message",
    ],
    cellRenderer: (key, value, row) => {
      if (key === "llm_batch_job_id") {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "product-link";
        button.textContent = `#${value}`;
        button.addEventListener("click", () => loadLlmBatchDetail(row.llm_batch_job_id));
        return button;
      }
      if (key === "status") {
        const wrap = document.createElement("div");
        wrap.className = "batch-actions";
        const status = document.createElement("span");
        status.textContent = display(value);
        wrap.appendChild(status);
        wrap.appendChild(batchActionButton("제출", () => submitLlmBatch(row.llm_batch_job_id), row.provider_batch_id));
        wrap.appendChild(batchActionButton("상태", () => refreshLlmBatch(row.llm_batch_job_id), false));
        wrap.appendChild(batchActionButton("Import", () => importLlmBatch(row.llm_batch_job_id), false));
        return wrap;
      }
      return document.createTextNode(display(value));
    },
  });
}

function batchActionButton(label, handler, disabled) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "secondary tiny-button";
  button.textContent = label;
  button.disabled = Boolean(disabled);
  button.addEventListener("click", handler);
  return button;
}

async function loadLlmBatchDetail(batchJobId) {
  try {
    const detail = await adminGetJson(`/api/admin/llm-batch-jobs/${batchJobId}`);
    renderTable(document.getElementById("llmBatchQueueTable"), detail.queues || [], {
      emptyText: "Batch queue 상세가 없습니다.",
      preferredKeys: ["llm_queue_id", "crawl_job_id", "status", "target_type", "target_id", "task_type", "priority", "last_error"],
    });
  } catch (error) {
    document.getElementById("llmBatchMessage").textContent = error.message;
  }
}

async function submitLlmBatch(batchJobId) {
  await mutateLlmBatch(`/api/admin/llm-batch-jobs/${batchJobId}/submit`, batchJobId, "Batch 제출 완료");
}

async function refreshLlmBatch(batchJobId) {
  await mutateLlmBatch(`/api/admin/llm-batch-jobs/${batchJobId}/refresh-status`, batchJobId, "Batch 상태 갱신 완료");
}

async function importLlmBatch(batchJobId) {
  await mutateLlmBatch(`/api/admin/llm-batch-jobs/${batchJobId}/import-results`, batchJobId, "Batch 결과 import 완료");
}

async function mutateLlmBatch(url, batchJobId, successMessage) {
  const message = document.getElementById("llmBatchMessage");
  try {
    await adminPostJson(url, {});
    message.textContent = successMessage;
    await refreshLlmBatchJobs();
    await loadLlmBatchDetail(batchJobId);
    await refreshLlmCostSummary();
  } catch (error) {
    message.textContent = error.message;
  }
}

function renderCrawlJobs(jobs) {
  renderTable(document.getElementById("crawlJobTable"), jobs, {
    emptyText: "최근 작업이 없습니다.",
    preferredKeys: [
      "crawl_job_id",
      "status",
      "job_name",
      "date_from",
      "date_to",
      "completed_tasks",
      "total_tasks",
      "failed_tasks",
      "total_api_calls",
      "total_items_fetched",
      "total_articles_saved",
      "total_articles_duplicated",
      "total_articles_out_of_range",
      "include_exclusive_right_pipeline",
      "exclusive_right_pipeline_mode",
      "exclusive_right_pipeline_status",
      "exclusive_right_candidate_count",
      "exclusive_right_queue_created_count",
      "exclusive_right_batch_job_id",
      "exclusive_right_batch_status",
      "exclusive_right_imported_count",
      "exclusive_right_canonical_count",
      "started_at",
      "finished_at",
      "error_message",
    ],
    cellRenderer: (key, value, row) => {
      if (key === "crawl_job_id") {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "product-link";
        button.textContent = `#${value}`;
        button.addEventListener("click", () => loadCrawlJobDetail(row.crawl_job_id));
        return button;
      }
      return document.createTextNode(display(value));
    },
  });
}

async function refreshLlmCostSummary() {
  const table = document.getElementById("llmCostTable");
  if (!table) return;
  const summary = await adminGetJson("/api/admin/llm-cost-summary");
  renderTable(table, [
    {
      total_estimated_cost_usd: summary.total_estimated_cost_usd,
      cache_hit_rate: summary.cache_hit_rate,
      batch_request_count: summary.batch_request_count,
      input_tokens_total: summary.input_tokens_total,
      output_tokens_total: summary.output_tokens_total,
      run_count: summary.run_count,
      extract_run_count: summary.extract_run_count,
      verify_run_count: summary.verify_run_count,
      estimate_quality: summary.estimate_quality,
      models: (summary.by_model || []).length,
      task_types: (summary.by_task_type || []).length,
    },
  ], {
    emptyText: "LLM 비용 로그가 없습니다.",
    preferredKeys: [
      "total_estimated_cost_usd",
      "cache_hit_rate",
      "batch_request_count",
      "input_tokens_total",
      "output_tokens_total",
      "run_count",
      "extract_run_count",
      "verify_run_count",
      "estimate_quality",
      "models",
      "task_types",
    ],
  });
}

async function refreshLlmSavingsSummary() {
  const summaryTable = document.getElementById("llmSavingsTable");
  const breakdownTable = document.getElementById("llmSavingsBreakdownTable");
  if (!summaryTable || !breakdownTable || !state.adminToken) return;
  const params = llmSavingsParams();
  const summary = await adminGetJson(`/api/admin/llm-cost-savings-summary?${params.toString()}`);
  renderTable(summaryTable, [
    {
      baseline_estimated_cost_usd: summary.baseline_estimated_cost_usd,
      optimized_actual_cost_usd: summary.optimized_actual_cost_usd,
      estimated_savings_usd: summary.estimated_savings_usd,
      estimated_savings_rate: `${Math.round((summary.estimated_savings_rate || 0) * 1000) / 10}%`,
      article_count: summary.counts?.article_count,
      llm_queue_count: summary.counts?.llm_queue_count,
      llm_run_count: summary.counts?.llm_run_count,
      cache_hit_count: summary.counts?.cache_hit_count,
      batch_run_count: summary.counts?.batch_run_count,
      estimate_quality: summary.estimate_quality,
    },
  ], {
    emptyText: "비용절감 계산 대상 로그가 없습니다.",
    preferredKeys: [
      "baseline_estimated_cost_usd",
      "optimized_actual_cost_usd",
      "estimated_savings_usd",
      "estimated_savings_rate",
      "article_count",
      "llm_queue_count",
      "llm_run_count",
      "cache_hit_count",
      "batch_run_count",
      "estimate_quality",
    ],
  });
  const breakdown = summary.breakdown || {};
  const rows = Object.entries(breakdown).map(([saving_type, estimated_savings_usd]) => ({ saving_type, estimated_savings_usd }));
  renderTable(breakdownTable, rows, {
    emptyText: "절감 기여도 데이터가 없습니다.",
    preferredKeys: ["saving_type", "estimated_savings_usd"],
  });
}

function llmSavingsParams() {
  const params = new URLSearchParams();
  params.set("baseline_policy", document.getElementById("llmBaselinePolicy").value);
  params.set("include_breakdown", "true");
  const range = document.getElementById("llmSavingsRange").value;
  const today = new Date();
  const formatDate = (date) => date.toISOString().slice(0, 10);
  if (range === "today") {
    params.set("date_from", formatDate(today));
    params.set("date_to", formatDate(today));
  } else if (range === "7" || range === "30") {
    const from = new Date(today);
    from.setDate(today.getDate() - Number(range) + 1);
    params.set("date_from", formatDate(from));
    params.set("date_to", formatDate(today));
  } else if (range === "custom") {
    const fromValue = document.getElementById("llmSavingsDateFrom").value;
    const toValue = document.getElementById("llmSavingsDateTo").value;
    if (fromValue) params.set("date_from", fromValue);
    if (toValue) params.set("date_to", toValue);
  }
  return params;
}

async function loadCrawlJobDetail(crawlJobId) {
  try {
    const detail = await adminGetJson(`/api/admin/crawl-jobs/${crawlJobId}`);
    renderTable(document.getElementById("crawlJobDetailTable"), [detail], {
      emptyText: "작업 상세가 없습니다.",
      preferredKeys: [
        "crawl_job_id",
        "status",
        "job_name",
        "date_from",
        "date_to",
        "include_exclusive_right_pipeline",
        "exclusive_right_pipeline_mode",
        "exclusive_right_pipeline_status",
        "exclusive_right_candidate_count",
        "exclusive_right_queue_created_count",
        "exclusive_right_batch_job_id",
        "exclusive_right_batch_status",
        "exclusive_right_imported_count",
        "exclusive_right_canonical_count",
        "exclusive_right_consolidation_job_id",
        "exclusive_right_pipeline_error",
      ],
    });
    renderTable(document.getElementById("crawlTaskTable"), detail.tasks || [], {
      emptyText: "작업 상세 task가 없습니다.",
      preferredKeys: [
        "crawl_task_id",
        "status",
        "company_name",
        "query_text",
        "api_calls",
        "items_fetched",
        "articles_saved",
        "articles_duplicated",
        "articles_out_of_range",
        "last_error",
      ],
    });
  } catch (error) {
    document.getElementById("adminJobMessage").textContent = error.message;
  }
}

async function adminGetJson(url) {
  const response = await fetch(url, { headers: { Authorization: `Bearer ${state.adminToken}` } });
  if (!response.ok) throw new Error(`관리자 요청 실패: ${response.status}`);
  return response.json();
}

async function adminPostJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${state.adminToken}` },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `관리자 요청 실패: ${response.status}`);
  }
  return response.json();
}

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`요청 실패: ${response.status}`);
  return response.json();
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `요청 실패: ${response.status}`);
  }
  return response.json();
}

function renderError(error) {
  const table = document.getElementById("productTable");
  table.innerHTML = `<tr><td>${escapeHtml(error.message)}</td></tr>`;
}

function setButtonLabel(button, label) {
  const target = button?.querySelector?.(".button-text");
  if (target) {
    target.textContent = label;
  } else if (button) {
    button.textContent = label;
  }
}

function display(value) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "boolean") return value ? "true" : "false";
  return String(value);
}

function number(value) {
  if (value === null || value === undefined || value === "") return "0";
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return display(value);
  return new Intl.NumberFormat("ko-KR").format(numeric);
}

function formatConfidence(value) {
  if (value === null || value === undefined || value === "") return "-";
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return display(value);
  return numeric.toFixed(2);
}

function escapeHtml(value) {
  return display(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
}
