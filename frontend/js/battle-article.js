import { fetchArticle } from "./api.js";
import { LANGUAGE_NAMES } from "./battle-labels.js";
import { displayTitle, titleNote, winnerText } from "./battle-model.js";

const LOADING = "Laden…";
const NO_ARTICLE = "Geen artikel beschikbaar voor deze veldslag.";
const LOAD_FAILED = "Artikel kon niet worden geladen.";
const TRANSLATING = "Nederlandse vertaling wordt gemaakt… dit kan een minuut duren.";
const NO_DUTCH = "Geen vertaling beschikbaar voor deze taal";
const SLOW_AFTER_MS = 1500;
const SOURCES = {
  en: "Bron: Engelse Wikipedia, CC BY-SA 4.0",
  nl: "Bron: Nederlandse Wikipedia, CC BY-SA 4.0",
  de: "Bron: Duitse Wikipedia, CC BY-SA 4.0",
  pl: "Bron: Poolse Wikipedia, CC BY-SA 4.0",
  ru: "Bron: Russische Wikipedia, CC BY-SA 4.0",
  fr: "Bron: Franse Wikipedia, CC BY-SA 4.0",
  it: "Bron: Italiaanse Wikipedia, CC BY-SA 4.0",
  ja: "Bron: Japanse Wikipedia, CC BY-SA 4.0",
};

function element(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) node.textContent = content;
  return node;
}

function newTabLink(href, text) {
  const link = element("a", "", text);
  link.setAttribute("href", href);
  link.setAttribute("target", "_blank");
  link.setAttribute("rel", "noopener noreferrer");
  return link;
}

// The article of the selected battle. The server sanitised the HTML with a whitelist, so it
// is the one text that goes into the page as markup (through a template, which runs no
// scripts and loads nothing). Titles, messages and the source line are text content.
function languageName(lang) {
  return (LANGUAGE_NAMES[lang] ?? lang.toUpperCase()).toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
}

// The article of the selected battle. The server sanitised the HTML with a whitelist, so it
// is the one text that goes into the page as markup (through a template, which runs no
// scripts and loads nothing). Titles, messages and the source line are text content.
// Two buttons choose between the original and its Dutch version (the Dutch Wikipedia's
// article, else a machine translation); the choice holds for the next articles too.
export function createArticlePane({ rootEl, load = fetchArticle, onBattleLink, onClose, onVersionChange }) {
  let latest = 0;
  let version = "origineel";
  let current = null;
  let pending = Promise.resolve();

  const title = element("h2", "article-title");
  const close = element("button", "article-close", "✕");
  close.setAttribute("type", "button");
  close.setAttribute("aria-label", "Sluit artikel");
  close.addEventListener("click", () => onClose?.());
  const langLabel = element("span", "article-lang");
  langLabel.hidden = true;
  const versions = element("div", "article-versions");
  versions.setAttribute("role", "group");
  versions.setAttribute("aria-label", "Taal van het artikel");
  const originalButton = element("button", "article-version", "Origineel");
  const dutchButton = element("button", "article-version", "NL");
  for (const [button, value] of [[originalButton, "origineel"], [dutchButton, "nl"]]) {
    button.setAttribute("type", "button");
    button.addEventListener("click", () => choose(value));
    versions.append(button);
  }
  versions.hidden = true;
  const head = element("div", "article-head");
  head.append(langLabel, title, versions, close);
  let sourceText = SOURCES.en;

  const winner = element("p", "article-winner");
  winner.hidden = true;
  const origin = element("p", "article-origin");
  origin.hidden = true;
  const status = element("p", "article-status");
  status.hidden = true;
  const body = element("div", "article-body");
  const source = element("p", "article-source");
  source.hidden = true;
  const scroll = element("div", "article-scroll");
  scroll.append(winner, origin, status, body, source);

  rootEl.replaceChildren(head, scroll);
  body.addEventListener("click", (event) => {
    const link = event.target.closest("a");
    if (!link) return;
    const battle = link.getAttribute("data-battle");
    if (battle === null) return;
    event.preventDefault();
    onBattleLink?.(battle);
  });

  function setStatus(text) {
    status.textContent = text;
    status.hidden = text === "";
  }

  function showSource(url, text = sourceText, label = "Origineel artikel") {
    source.replaceChildren(`${text} · `, newTabLink(url, label));
    source.hidden = false;
  }

  function showVersions(shown, available) {
    originalButton.setAttribute("aria-pressed", String(shown === "origineel"));
    dutchButton.setAttribute("aria-pressed", String(shown === "nl"));
    dutchButton.disabled = !available;
    dutchButton.setAttribute("title", available ? "Nederlandse versie" : NO_DUTCH);
  }

  function showOrigin(article, lang) {
    if (article.source === "wikipedia") {
      origin.replaceChildren("Nederlandse Wikipedia: ", newTabLink(article.url, article.title));
    } else {
      const via = lang === "en" ? "" : " (via het Engels)";
      origin.replaceChildren(`Machinevertaling uit het ${languageName(lang)}${via}`);
    }
    origin.hidden = false;
  }

  function choose(value) {
    if (value === version) return;
    version = value;
    onVersionChange?.(value);
    if (current) pending = present(current);
  }

  function render(html) {
    const template = document.createElement("template");
    template.innerHTML = html;
    body.replaceChildren(template.content);
    for (const link of body.querySelectorAll("a")) {
      if (link.getAttribute("data-battle") !== null) continue;
      link.setAttribute("target", "_blank");
      link.setAttribute("rel", "noopener noreferrer");
    }
  }

  async function present(battle) {
    const ticket = ++latest;
    const lang = battle.lang ?? "en";
    title.textContent = displayTitle(battle);
    title.setAttribute("title", titleNote(battle) ?? "");
    langLabel.textContent = lang.toUpperCase();
    langLabel.hidden = lang === "en";
    versions.hidden = lang === "nl";
    sourceText = SOURCES[lang] ?? `Bron: Wikipedia (${lang}), CC BY-SA 4.0`;
    winner.textContent = winnerText(battle.winner);
    winner.hidden = false;
    origin.hidden = true;
    body.replaceChildren();
    source.hidden = true;
    setStatus(LOADING);
    const wantDutch = version === "nl" && lang !== "nl";
    const slow = wantDutch ? setTimeout(() => ticket === latest && setStatus(TRANSLATING), SLOW_AFTER_MS) : null;
    let article;
    let dutch = false;
    try {
      if (wantDutch) {
        article = await load(battle.title, lang, "nl");
        dutch = article !== null;
      }
      if (!dutch) article = await load(battle.title, lang, "origineel");
    } catch {
      if (ticket !== latest) return;
      setStatus(LOAD_FAILED);
      showSource(battle.url);
      return;
    } finally {
      clearTimeout(slow);
    }
    if (ticket !== latest) return;
    if (article === null) {
      setStatus(NO_ARTICLE);
      showSource(battle.url);
      return;
    }
    setStatus("");
    render(article.html);
    showVersions(dutch ? "nl" : "origineel", dutch || article.dutch === true);
    if (dutch) {
      showOrigin(article, lang);
      if (article.source === "wikipedia") showSource(article.url, SOURCES.nl, "Nederlands artikel");
      else showSource(article.url, `${sourceText} · machinevertaling`);
    } else {
      showSource(article.url);
      if (wantDutch) {
        origin.replaceChildren(`${NO_DUTCH}; het origineel staat hieronder.`);
        origin.hidden = false;
      }
    }
  }

  return {
    show(battle) {
      current = battle;
      pending = present(battle);
      return pending;
    },
    // Sets the version for the next article (from the URL or the last choice), without telling.
    setVersion(value) {
      version = value === "nl" ? "nl" : "origineel";
    },
    version: () => version,
    settled: () => pending,
    clear() {
      latest += 1;
      current = null;
      origin.hidden = true;
      title.textContent = "";
      winner.hidden = true;
      body.replaceChildren();
      source.hidden = true;
      setStatus("");
    },
  };
}
