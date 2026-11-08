
document.addEventListener("DOMContentLoaded", () => {
	const searchForm = document.querySelector(".search-form");
	const searchInput = document.querySelector(".search-input");
	const resultsContainer = document.getElementById("results");

	const bookModal = document.getElementById("bookModal");
	const bookModalClose = document.getElementById("bookModalClose");

	function safeSetResultsHTML(html) {
		if (resultsContainer) {
			resultsContainer.innerHTML = html;
		}
	}

	function clearResults() {
		if (resultsContainer) resultsContainer.innerHTML = "";
	}

	function renderResults(items) {
		clearResults();
		if (!items || items.length === 0) {
			safeSetResultsHTML('<p class="muted">검색 결과가 없습니다.</p>');
			return;
		}

		const list = document.createElement("div");
		list.className = "results-list";

		items.forEach((item) => {
			const info = item.volumeInfo || {};
			const thumbnail = (info.imageLinks && (info.imageLinks.thumbnail || info.imageLinks.smallThumbnail)) || "";
			const title = info.title || "제목 없음";
			const authors = (info.authors && info.authors.join(", ")) || "저자 정보 없음";
			const publishedDate = info.publishedDate || "";
			const snippet = (item.searchInfo && item.searchInfo.textSnippet) || (info.description ? (info.description.substring(0, 200) + '...') : "");

			const card = document.createElement("div");
			card.className = "result-card";
			card.tabIndex = 0;

			const img = document.createElement("img");
			img.className = "result-thumb";
			img.src = thumbnail || "/referenceFinder/src/images/book-placeholder.png";
			img.alt = title;

			const meta = document.createElement("div");
			meta.className = "result-meta";

			const t = document.createElement("div");
			t.className = "result-title";
			t.textContent = title;

			const a = document.createElement("div");
			a.className = "result-authors";
			a.textContent = authors + (publishedDate ? ` · ${publishedDate}` : "");

			const s = document.createElement("div");
			s.className = "result-snippet";
			s.innerHTML = snippet;

			meta.appendChild(t);
			meta.appendChild(a);
			if (s.textContent) meta.appendChild(s);

			card.appendChild(img);
			card.appendChild(meta);

			card.addEventListener("click", () => openBookModal(item));
			card.addEventListener("keypress", (e) => {
				if (e.key === "Enter") openBookModal(item);
			});

			list.appendChild(card);
		});

		if (resultsContainer) {
			resultsContainer.appendChild(list);
		}
	}

	async function searchBooks(q) {
		if (!q || q.trim() === "") return renderResults([]);
		const btn = document.querySelector('.search-button');
		if (btn) btn.classList.add('loading');
		try {
			const res = await fetch(`https://www.googleapis.com/books/v1/volumes?q=${encodeURIComponent(q)}&maxResults=12`);
			const data = await res.json();
			renderResults(data.items || []);
		} catch (err) {
			safeSetResultsHTML('<p class="muted">오류가 발생했습니다.</p>');
		} finally {
			if (btn) btn.classList.remove('loading');
		}
	}

	if (searchForm) {
		searchForm.addEventListener("submit", (e) => {
			e.preventDefault();
			if (searchInput) searchBooks(searchInput.value);
		});
	} else if (searchInput) {
		searchInput.addEventListener('keydown', (e) => {
			if (e.key === 'Enter') searchBooks(searchInput.value);
		});
	}

	function openBookModal(item) {
		const info = item.volumeInfo || {};
		const titleEl = document.getElementById("bookModalBookTitle");
		const authorsEl = document.getElementById("bookModalAuthors");
		const yearEl = document.getElementById("bookModalYear");
		const snippetEl = document.getElementById("bookModalSnippet");
		const imageEl = document.getElementById("bookModalImage");

		if (titleEl) titleEl.textContent = info.title || "제목 없음";
		if (authorsEl) authorsEl.textContent = (info.authors && info.authors.join(", ")) || "저자 정보 없음";
		if (yearEl) yearEl.textContent = info.publishedDate || "";
		if (snippetEl) snippetEl.innerHTML = (item.searchInfo && item.searchInfo.textSnippet) || "";
		const thumbnail = (info.imageLinks && (info.imageLinks.thumbnail || info.imageLinks.smallThumbnail)) || "";
		if (imageEl) imageEl.src = thumbnail || "/referenceFinder/src/images/book-placeholder.png";

		if (bookModal) {
			bookModal.classList.add('active');
			bookModal.setAttribute("aria-hidden", "false");
			document.body.style.overflow = 'hidden';
		}
	}

	function closeBookModal() {
		if (!bookModal) return;
		bookModal.classList.remove('active');
		bookModal.setAttribute("aria-hidden", "true");
		document.body.style.overflow = '';
	}

	if (bookModalClose) bookModalClose.addEventListener("click", closeBookModal);
	if (bookModal) {
		bookModal.addEventListener("click", (e) => {
			if (e.target === bookModal) closeBookModal();
		});
	}

	document.addEventListener("keydown", (e) => {
		if (e.key === "Escape" && bookModal && bookModal.classList.contains("active")) closeBookModal();
	});
});

