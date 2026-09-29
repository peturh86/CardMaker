/* Starfsmannakort — frontend for the CardMaker API. No build step, no deps. */

const $ = (id) => document.getElementById(id);

const el = {
  adStatus: $("ad-status"),
  searchField: $("search-field"),
  search: $("search"),
  searchSpinner: $("search-spinner"),
  searchHint: $("search-hint"),
  results: $("results"),
  name: $("name"),
  kt: $("kt"),
  ktHint: $("kt-hint"),
  title: $("title"),
  dropzone: $("dropzone"),
  dropzoneEmpty: $("dropzone-empty"),
  photo: $("photo"),
  photoThumb: $("photo-thumb"),
  photoMeta: $("photo-meta"),
  photoSource: $("photo-source"),
  photoName: $("photo-name"),
  photoClear: $("photo-clear"),
  printer: $("printer"),
  removeBg: $("remove-bg"),
  btnReset: $("btn-reset"),
  btnPreview: $("btn-preview"),
  btnPrint: $("btn-print"),
  btnDownload: $("btn-download"),
  cardImg: $("card-img"),
  cardPlaceholder: $("card-placeholder"),
  cardLoading: $("card-loading"),
  previewNote: $("preview-note"),
  toasts: $("toasts"),
};

/** Selected photo: a File or Blob plus a label for the UI. */
let photo = null;
/** Object URLs we own and must revoke. */
let thumbUrl = null;
let cardUrl = null;

let searchAbort = null;
let previewAbort = null;
let searchTimer = null;
let previewTimer = null;

/* ── Helpers ─────────────────────────────────────────────────── */

function toast(message, kind = "info") {
  const node = document.createElement("div");
  node.className = `toast ${kind}`;
  node.textContent = message;
  el.toasts.append(node);
  setTimeout(() => {
    node.classList.add("out");
    node.addEventListener("animationend", () => node.remove());
  }, kind === "err" ? 6000 : 3500);
}

/** Pull a human-readable message out of a FastAPI error response. */
async function errorMessage(response, fallback) {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) return body.detail.map((d) => d.msg).join("; ");
  } catch {
    /* not JSON — fall through */
  }
  return `${fallback} (HTTP ${response.status})`;
}

function initials(name) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");
}

/* ── Boot: AD availability + printer list ────────────────────── */

async function boot() {
  prefillFromQuery();
  try {
    const status = await fetch("/api/status").then((r) => r.json());
    setAdStatus(status.ad_configured);
    fillPrinters(status.printers, status.default_printer);
  } catch {
    setAdStatus(false);
    fillPrinters([], "ZC300");
    toast("Could not reach the API.", "err");
  }
}

/** Allow ?name=…&kt=…&title=… so a card can be linked to directly. */
function prefillFromQuery() {
  const params = new URLSearchParams(location.search);
  let filled = false;
  for (const key of ["name", "kt", "title"]) {
    const value = params.get(key);
    if (value) {
      el[key].value = value;
      filled = true;
    }
  }
  if (params.get("kt")) el.kt.dispatchEvent(new Event("input"));
  if (filled) schedulePreview(0);
}

function setAdStatus(configured) {
  if (configured) {
    el.adStatus.className = "pill pill-green";
    el.adStatus.textContent = "Directory connected";
  } else {
    el.adStatus.className = "pill pill-red";
    el.adStatus.textContent = "Directory offline";
    el.search.disabled = true;
    el.search.placeholder = "Unavailable";
    el.searchHint.textContent = "Azure AD is not configured — enter card details manually.";
    el.searchHint.classList.add("warn");
  }
}

function fillPrinters(printers, defaultPrinter) {
  const names = printers && printers.length ? printers : [defaultPrinter];
  el.printer.replaceChildren(
    ...names.map((name) => {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name === defaultPrinter ? `${name} (default)` : name;
      option.selected = name === defaultPrinter;
      return option;
    })
  );
  if (!printers || !printers.length) {
    el.printer.after(Object.assign(document.createElement("p"), {
      className: "hint warn",
      textContent: "No CUPS printers detected — printing will fail.",
    }));
  }
}

/* ── Directory search ────────────────────────────────────────── */

el.search.addEventListener("input", () => {
  clearTimeout(searchTimer);
  const query = el.search.value.trim();
  if (query.length < 2) {
    hideResults();
    return;
  }
  searchTimer = setTimeout(() => runSearch(query), 300);
});

el.search.addEventListener("keydown", (event) => {
  if (event.key === "Escape") hideResults();
});

document.addEventListener("click", (event) => {
  if (!el.searchField.contains(event.target)) hideResults();
});

function hideResults() {
  el.results.hidden = true;
  el.results.replaceChildren();
}

async function runSearch(query) {
  searchAbort?.abort();
  searchAbort = new AbortController();
  el.searchSpinner.hidden = false;

  try {
    const response = await fetch(`/search-employees?q=${encodeURIComponent(query)}`, {
      signal: searchAbort.signal,
    });
    if (!response.ok) {
      toast(await errorMessage(response, "Search failed"), "err");
      hideResults();
      return;
    }
    renderResults((await response.json()).results);
  } catch (error) {
    if (error.name !== "AbortError") toast("Search request failed.", "err");
  } finally {
    el.searchSpinner.hidden = true;
  }
}

function renderResults(results) {
  el.results.hidden = false;

  if (!results.length) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent = "No matches";
    el.results.replaceChildren(empty);
    return;
  }

  el.results.replaceChildren(...results.map((employee) => {
    const item = document.createElement("li");
    item.tabIndex = 0;

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    if (employee.has_photo) {
      const img = document.createElement("img");
      img.src = `/search-employees/${encodeURIComponent(employee.id)}/photo`;
      img.alt = "";
      img.addEventListener("error", () => { avatar.textContent = initials(employee.name); });
      avatar.append(img);
    } else {
      avatar.textContent = initials(employee.name);
    }

    const text = document.createElement("div");
    text.className = "result-text";
    const name = document.createElement("div");
    name.className = "result-name";
    name.textContent = employee.name;
    const sub = document.createElement("div");
    sub.className = "result-sub";
    sub.textContent = [employee.title, employee.kt].filter(Boolean).join(" · ") || employee.upn;
    text.append(name, sub);

    item.append(avatar, text);
    const choose = () => selectEmployee(employee);
    item.addEventListener("click", choose);
    item.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); choose(); }
    });
    return item;
  }));
}

async function selectEmployee(employee) {
  el.name.value = employee.name;
  el.kt.value = employee.kt;
  el.title.value = employee.title;
  el.search.value = employee.name;
  hideResults();

  if (employee.has_photo) {
    try {
      const response = await fetch(`/search-employees/${encodeURIComponent(employee.id)}/photo`);
      if (response.ok) {
        setPhoto(await response.blob(), "Directory photo", employee.name, "Directory");
      }
    } catch {
      toast("Could not load the directory photo.", "err");
    }
  } else {
    clearPhoto();
  }

  schedulePreview(0);
}

/* ── Photo handling ──────────────────────────────────────────── */

function setPhoto(blob, label, description, sourceKind) {
  photo = { blob, filename: label };

  if (thumbUrl) URL.revokeObjectURL(thumbUrl);
  thumbUrl = URL.createObjectURL(blob);

  el.photoThumb.src = thumbUrl;
  el.photoThumb.hidden = false;
  el.dropzoneEmpty.hidden = true;
  el.dropzone.classList.add("has-photo");
  el.photoMeta.hidden = false;
  el.photoSource.textContent = sourceKind;
  el.photoName.textContent = description;
}

function clearPhoto() {
  photo = null;
  if (thumbUrl) { URL.revokeObjectURL(thumbUrl); thumbUrl = null; }
  el.photoThumb.hidden = true;
  el.photoThumb.removeAttribute("src");
  el.dropzoneEmpty.hidden = false;
  el.dropzone.classList.remove("has-photo");
  el.photoMeta.hidden = true;
  el.photo.value = "";
}

function acceptFile(file) {
  if (!file) return;
  if (!file.type.startsWith("image/")) {
    toast("That file is not an image.", "err");
    return;
  }
  setPhoto(file, file.name, file.name, "Uploaded");
  schedulePreview(0);
}

el.dropzone.addEventListener("click", () => el.photo.click());
el.dropzone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") { event.preventDefault(); el.photo.click(); }
});
el.photo.addEventListener("change", () => acceptFile(el.photo.files[0]));

["dragenter", "dragover"].forEach((type) =>
  el.dropzone.addEventListener(type, (event) => {
    event.preventDefault();
    el.dropzone.classList.add("dragging");
  })
);
["dragleave", "drop"].forEach((type) =>
  el.dropzone.addEventListener(type, () => el.dropzone.classList.remove("dragging"))
);
el.dropzone.addEventListener("drop", (event) => {
  event.preventDefault();
  acceptFile(event.dataTransfer.files[0]);
});

el.photoClear.addEventListener("click", (event) => {
  event.stopPropagation();
  clearPhoto();
  schedulePreview(0);
});

/* ── Kennitala formatting ────────────────────────────────────── */

el.kt.addEventListener("input", () => {
  const digits = el.kt.value.replace(/\D/g, "").slice(0, 10);
  el.kt.value = digits.length > 6 ? `${digits.slice(0, 6)}-${digits.slice(6)}` : digits;
  const valid = digits.length === 0 || digits.length === 10;
  el.kt.classList.toggle("invalid", !valid);
  el.ktHint.textContent = valid
    ? "Encoded as the Code128 barcode."
    : `${digits.length}/10 digits`;
  el.ktHint.classList.toggle("warn", !valid);
});

/* ── Card generation ─────────────────────────────────────────── */

function formData(extra = {}) {
  const data = new FormData();
  data.set("name", el.name.value.trim());
  data.set("kt", el.kt.value.trim());
  data.set("title", el.title.value.trim());
  data.set("remove_bg", el.removeBg.checked ? "true" : "false");
  if (photo) data.append("photo", photo.blob, photo.filename || "photo.jpg");
  for (const [key, value] of Object.entries(extra)) data.set(key, value);
  return data;
}

function schedulePreview(delay = 500) {
  clearTimeout(previewTimer);
  if (el.removeBg.checked) {
    // Background removal is far too slow to run on every keystroke.
    el.previewNote.textContent = "Background removal is on — click Preview to render.";
    return;
  }
  el.previewNote.textContent = "Preview updates as you type.";
  previewTimer = setTimeout(renderPreview, delay);
}

async function renderPreview() {
  clearTimeout(previewTimer);
  if (!el.name.value.trim()) {
    showPlaceholder();
    return;
  }

  previewAbort?.abort();
  previewAbort = new AbortController();
  el.cardLoading.hidden = false;

  try {
    const response = await fetch("/generate-card", {
      method: "POST",
      body: formData(),
      signal: previewAbort.signal,
    });
    if (!response.ok) {
      toast(await errorMessage(response, "Could not generate the card"), "err");
      return;
    }
    showCard(await response.blob());
  } catch (error) {
    if (error.name !== "AbortError") toast("Card generation failed.", "err");
  } finally {
    el.cardLoading.hidden = true;
  }
}

function showCard(blob) {
  if (cardUrl) URL.revokeObjectURL(cardUrl);
  cardUrl = URL.createObjectURL(blob);
  el.cardImg.src = cardUrl;
  el.cardImg.hidden = false;
  el.cardPlaceholder.hidden = true;
  el.btnDownload.hidden = false;
  el.btnDownload.href = cardUrl;

  const slug = el.name.value.trim().replace(/\s+/g, "_") || "starfsmannakort";
  el.btnDownload.download = `${slug}.jpg`;
}

function showPlaceholder() {
  if (cardUrl) { URL.revokeObjectURL(cardUrl); cardUrl = null; }
  el.cardImg.hidden = true;
  el.cardImg.removeAttribute("src");
  el.cardPlaceholder.hidden = false;
  el.btnDownload.hidden = true;
}

[el.name, el.kt, el.title].forEach((input) =>
  input.addEventListener("input", () => schedulePreview())
);
el.removeBg.addEventListener("change", () => schedulePreview(0));
el.btnPreview.addEventListener("click", renderPreview);

/* ── Printing ────────────────────────────────────────────────── */

el.btnPrint.addEventListener("click", async () => {
  if (!el.name.value.trim()) {
    toast("Enter a name first.", "err");
    el.name.focus();
    return;
  }

  el.btnPrint.disabled = true;
  el.cardLoading.hidden = false;
  try {
    const response = await fetch("/generate-and-print-card", {
      method: "POST",
      body: formData({ printer_name: el.printer.value }),
    });
    if (!response.ok) {
      toast(await errorMessage(response, "Printing failed"), "err");
      return;
    }
    showCard(await response.blob());
    toast(`Card sent to ${el.printer.value}.`, "ok");
  } catch {
    toast("Print request failed.", "err");
  } finally {
    el.btnPrint.disabled = false;
    el.cardLoading.hidden = true;
  }
});

/* ── Reset ───────────────────────────────────────────────────── */

el.btnReset.addEventListener("click", () => {
  el.search.value = "";
  el.name.value = "";
  el.kt.value = "";
  el.title.value = "";
  el.removeBg.checked = false;
  el.ktHint.textContent = "Encoded as the Code128 barcode.";
  el.ktHint.classList.remove("warn");
  el.kt.classList.remove("invalid");
  hideResults();
  clearPhoto();
  showPlaceholder();
  el.previewNote.textContent = "Preview updates as you type.";
});

boot();
