const steamKeyInput = document.querySelector("#steamKey");
const deepseekKeyInput = document.querySelector("#deepseekKey");
const steamIdsInput = document.querySelector("#steamIds");
const requiredPlayersInput = document.querySelector("#requiredPlayers");
const includeFreshInput = document.querySelector("#includeFresh");
const excludeOwnedInput = document.querySelector("#excludeOwned");
const boostTagsInput = document.querySelector("#boostTags");
const passTagsInput = document.querySelector("#passTags");
const statusEl = document.querySelector("#status");
const runButton = document.querySelector("#runButton");
const tagsEl = document.querySelector("#tags");
const distributionEl = document.querySelector("#distribution");
const recommendationsEl = document.querySelector("#recommendations");
const freshRecommendationsEl = document.querySelector("#freshRecommendations");
const tagSuggestionsEl = document.querySelector("#tagSuggestions");
const boostTagHintsEl = document.querySelector("#boostTagHints");
const passTagHintsEl = document.querySelector("#passTagHints");

const tagSuggestions = [
  "生存", "生存合作", "生存建造", "开放世界生存", "合作", "双人合作", "派对合作",
  "社交合作", "合作射击", "动作", "动作冒险", "动作 Roguelike", "冒险", "独立",
  "角色扮演", "在线角色扮演", "大型多人在线", "策略", "多人策略", "竞技",
  "竞技射击", "战术合作", "格斗", "派对", "休闲", "模拟", "体育", "抢先体验"
];

steamKeyInput.value = sessionStorage.getItem("steam_api_key") || "";
deepseekKeyInput.value = sessionStorage.getItem("deepseek_api_key") || "";

function track(event, meta) {
  try {
    fetch("/api/track", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({event, meta: meta || {}}),
      keepalive: true
    });
  } catch (e) { /* 埋点失败不影响功能 */ }
}

steamIdsInput.addEventListener("input", () => track("ids_input", {}), {once: true});
tagSuggestionsEl.innerHTML = tagSuggestions.map((tag) => `<option value="${escapeHtml(tag)}"></option>`).join("");
setupTagHints(boostTagsInput, boostTagHintsEl);
setupTagHints(passTagsInput, passTagHintsEl);

runButton.addEventListener("click", async () => {
  const steam_api_key = steamKeyInput.value.trim();
  const deepseek_api_key = deepseekKeyInput.value.trim();
  const steam_ids = steamIdsInput.value.split(/\s|,|，/).map((item) => item.trim()).filter(Boolean);
  const required_players = requiredPlayersInput.value ? Number(requiredPlayersInput.value) : null;
  const include_fresh = includeFreshInput.checked;
  const exclude_owned = excludeOwnedInput.checked;
  const boost_tags = splitTags(boostTagsInput.value);
  const pass_tags = splitTags(passTagsInput.value);

  track("submit_click", {
    entries: steam_ids.length,
    sample: steam_ids.slice(0, 5),
    has_own_key: !!steam_api_key,
    has_ai_key: !!deepseek_api_key,
    include_fresh,
    exclude_owned
  });

  if (steam_ids.length < 2) {
    statusEl.textContent = "至少输入 2 个 Steam ID 或个人主页链接。";
    track("client_blocked", {reason: "ids_less_than_2", entries: steam_ids.length, raw: steamIdsInput.value.slice(0, 300)});
    return;
  }

  sessionStorage.setItem("steam_api_key", steam_api_key);
  sessionStorage.setItem("deepseek_api_key", deepseek_api_key);
  runButton.disabled = true;
  statusEl.textContent = "正在读取库存、刷新游戏属性并计算推荐...";
  recommendationsEl.innerHTML = "";
  freshRecommendationsEl.innerHTML = "";

  try {
    const response = await fetch("/api/recommend", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        steam_api_key,
        deepseek_api_key,
        steam_ids,
        include_fresh,
        exclude_owned,
        required_players,
        boost_tags,
        pass_tags
      })
    });
    const data = await response.json();
    if (!response.ok) {
      const error = new Error(data.detail || "推荐失败");
      error.code = data.error_code;
      throw error;
    }
    renderTags(data.group_tags, data.distribution);
    renderCards(recommendationsEl, data.recommendations, "main");
    renderCards(freshRecommendationsEl, data.fresh_recommendations || [], "fresh");
    const excluded = data.excluded_players.length ? `，排除 ${data.excluded_players.length} 个数据不足或私密玩家` : "";
    const ai = data.ai_status ? ` ${data.ai_status}` : "";
    statusEl.textContent = `完成：有效玩家 ${data.valid_players.length} 人${excluded}。${ai}`;
  } catch (error) {
    track("client_error", {code: error.code || "", message: String(error.message).slice(0, 200)});
    if (error.code === "fallback_key_failed" || error.code === "user_key_needed") {
      statusEl.innerHTML = `${escapeHtml(error.message)} <a href="https://steamcommunity.com/dev/apikey" target="_blank" rel="noreferrer">点这里申请自己的 key</a>`;
      steamKeyInput.focus();
    } else {
      statusEl.textContent = error.message;
    }
  } finally {
    runButton.disabled = false;
  }
});

function splitTags(value) {
  return value.split(/,|，/).map((item) => item.trim()).filter(Boolean);
}

function setupTagHints(input, target) {
  const render = () => {
    const current = input.value.split(/,|，/).pop().trim().toLowerCase();
    const selected = new Set(splitTags(input.value));
    const matches = tagSuggestions
      .filter((tag) => !selected.has(tag))
      .filter((tag) => !current || tag.toLowerCase().includes(current) || current.includes(tag.toLowerCase()))
      .slice(0, 8);
    target.innerHTML = matches.map((tag) => `<button class="hint-button" type="button" data-tag="${escapeHtml(tag)}">${escapeHtml(tag)}</button>`).join("");
  };
  input.addEventListener("input", render);
  input.addEventListener("focus", render);
  target.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-tag]");
    if (!button) {
      return;
    }
    const parts = input.value.split(/,|，/).map((item) => item.trim()).filter(Boolean);
    if (!parts.includes(button.dataset.tag)) {
      parts.push(button.dataset.tag);
    }
    input.value = parts.join(",");
    render();
    input.focus();
  });
  render();
}

function renderTags(tags, distribution) {
  distributionEl.textContent = distributionLabel(distribution);
  tagsEl.innerHTML = tags.map(([tag, value]) => `<span class="tag">${escapeHtml(tag)} ${(value * 100).toFixed(1)}%</span>`).join("");
}

function renderCards(target, items, variant) {
  if (!items.length) {
    target.innerHTML = `<p class="muted">暂无结果。</p>`;
    return;
  }
  target.innerHTML = items.map((item, index) => {
    const image = item.capsule_image ? `<img src="${item.capsule_image}" alt="">` : "";
    const tags = item.tags.slice(0, 4).map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join("");
    const marks = item.source_marks.slice(0, 2).map((mark) => `<span class="tag">${escapeHtml(mark)}</span>`).join("");
    const reviews = item.review_percent ? `<span class="tag">近期口碑 ${item.review_percent}/10</span>` : "";
    const price = priceHtml(item);
    const fitPercent = Number(item.fit_percent || 0);
    const fit = fitPercent ? `<span class="fit-meter" style="--fit:${fitPercent}"><strong>${fitPercent}</strong><small>%</small></span>` : "";
    return `
      <article class="card game-card ${variant === "fresh" ? "fresh-card" : ""}">
        <div class="card-media">
          ${image}
          <span class="rank">#${String(index + 1).padStart(2, "0")}</span>
          ${fit}
        </div>
        <div class="card-body">
          <h3><a href="${item.store_url}" target="_blank" rel="noreferrer">${escapeHtml(item.name)}</a></h3>
          <div class="meta">${price}${reviews}${marks}${tags}</div>
          <p class="reason">${escapeHtml(item.reason)}</p>
        </div>
      </article>
    `;
  }).join("");
}

function priceHtml(item) {
  if (item.price_final === null || item.price_final === undefined) {
    return "";
  }
  if (item.price_final === 0) {
    return `<span class="tag price-tag">免费</span>`;
  }
  const symbol = item.price_currency === "CNY" ? "¥" : `${item.price_currency || ""} `;
  const fmt = (cents) => `${symbol}${(cents / 100).toFixed(2)}`;
  let html = `<span class="tag price-tag">现价 ${fmt(item.price_final)}`;
  if (item.price_discount) {
    html += ` <s>${fmt(item.price_initial)}</s> −${item.price_discount}%`;
  }
  html += `</span>`;
  if (item.price_lowest !== null && item.price_lowest !== undefined) {
    if (item.price_lowest < item.price_final) {
      html += `<span class="tag">观测史低 ${fmt(item.price_lowest)}</span>`;
    } else {
      html += `<span class="tag">现价即观测史低</span>`;
    }
  }
  return html;
}

function distributionLabel(value) {
  return {
    focused: "口味集中",
    mixed: "口味混合",
    diverse: "口味分散",
    insufficient: "数据不足"
  }[value] || value || "等待计算";
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  }[char]));
}
