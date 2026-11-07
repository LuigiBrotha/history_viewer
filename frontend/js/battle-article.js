import { fetchArticle } from "./api.js";
import { winnerText } from "./battle-model.js";

const LOADING = "Laden…";
const NO_ARTICLE = "Geen artikel beschikbaar voor deze veldslag.";
const LOAD_FAILED = "Artikel kon niet worden geladen.";
const SOURCES = {
  en: "Bron: Engelse Wikipedia, CC BY-SA 4.0",
  nl: "Bron: Nederlandse Wikipedia, CC BY-SA 4.0",
  de: "Bron: Duitse Wikipedia, CC BY-SA 4.0",
  pl: "Bron: Poolse Wikipedia, CC BY-SA 4.0",
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
export function createArticlePane({ rootEl, load = fetchArticle, onBattleLink, onClose }) {
  let latest = 0;

  const title = element("h2", "article-title");
  const close = element("button", "article-close", "✕");
  close.setAttribute("type", "button");
  close.setAttribute("aria-label", "Sluit artikel");
  close.addEventListener("click", () => onClose?.());
  const langLabel = element("span", "article-lang");
  langLabel.hidden = true;
  const head = element("div", "article-head");
  head.append(langLabel, title, close);
  let sourceText = SOURCES.en;

  const winner = element("p", "article-winner");
  winner.hidden = true;
  const status = element("p", "article-status");
  status.hidden = true;
  const body = element("div", "article-body");
  const source = element("p", "article-source");
  source.hidden = true;
  const scroll = element("div", "article-scroll");
  scroll.append(winner, status, body, source);

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

  function showSource(url) {
    source.replaceChildren(`${sourceText} · `, newTabLink(url, "Origineel artikel"));
    source.hidden = false;
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

  return {
    async show(battle) {
      const ticket = ++latest;
      const lang = battle.lang ?? "en";
      title.textContent = battle.title;
      langLabel.textContent = lang.toUpperCase();
      langLabel.hidden = lang === "en";
      sourceText = SOURCES[lang] ?? SOURCES.en;
      winner.textContent = winnerText(battle.winner);
      winner.hidden = false;
      body.replaceChildren();
      source.hidden = true;
      setStatus(LOADING);
      let article;
      try {
        article = await load(battle.title, lang);
      } catch {
        if (ticket !== latest) return;
        setStatus(LOAD_FAILED);
        showSource(battle.url);
        return;
      }
      if (ticket !== latest) return;
      if (article === null) {
        setStatus(NO_ARTICLE);
        showSource(battle.url);
        return;
      }
      setStatus("");
      render(article.html);
      showSource(article.url);
    },
    clear() {
      latest += 1;
      title.textContent = "";
      winner.hidden = true;
      body.replaceChildren();
      source.hidden = true;
      setStatus("");
    },
  };
}
