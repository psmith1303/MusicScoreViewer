// ---------------------------------------------------------------------------
// View management — switches between library, setlists, recent, and viewer
// ---------------------------------------------------------------------------

import { getState } from "./state.js";
import {
  libraryView, setlistView, recentView, newestView, viewerView,
  btnLibrary, btnSetlists, btnRecent, btnNewest, titleDisplay, pdfContainer,
} from "./dom.js";

export function showView(view) {
  const s = getState();
  s.currentView = view;

  libraryView.classList.add("hidden");
  setlistView.classList.add("hidden");
  recentView.classList.add("hidden");
  newestView.classList.add("hidden");
  viewerView.classList.add("hidden");

  btnLibrary.classList.remove("active");
  btnSetlists.classList.remove("active");
  btnRecent.classList.remove("active");
  btnNewest.classList.remove("active");

  switch (view) {
    case "library":
      libraryView.classList.remove("hidden");
      btnLibrary.classList.add("active");
      titleDisplay.textContent = s.appTitle;
      break;
    case "setlists":
      setlistView.classList.remove("hidden");
      btnSetlists.classList.add("active");
      titleDisplay.textContent = s.appTitle;
      break;
    case "recent":
      recentView.classList.remove("hidden");
      btnRecent.classList.add("active");
      titleDisplay.textContent = s.appTitle;
      break;
    case "newest":
      newestView.classList.remove("hidden");
      btnNewest.classList.add("active");
      titleDisplay.textContent = s.appTitle;
      break;
    case "viewer":
      viewerView.classList.remove("hidden");
      pdfContainer.focus();
      break;
  }
}
