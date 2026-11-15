// Northstar Shoes demo storefront. Deliberately agent-unfriendly: client-only
// rendering, clickable divs instead of links and buttons, an unlabeled custom size
// picker, an offer pop-up, and a delivery check that requires signing in.
const app = document.getElementById("app");
const money = (value) => `₹${value.toLocaleString("en-IN")}`;
const go = (path) => { history.pushState({}, "", path); render(); };
window.addEventListener("popstate", render);

async function api(path, options = {}) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json" }, credentials: "same-origin", ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw Object.assign(new Error(data.detail || "Request failed"), { status: response.status });
  return data;
}

function layout(content) {
  app.innerHTML = `
    <header>
      <div class="logo" data-go="/">Northstar Shoes</div>
      <nav><span data-go="/policies">Help</span><span data-go="/delivery">Delivery</span><span data-go="/cart">Cart</span></nav>
    </header>
    <main>${content}</main>`;
  app.querySelectorAll("[data-go]").forEach((el) => el.addEventListener("click", () => go(el.dataset.go)));
}

async function home() {
  const { products } = await api("/api/products");
  layout(`<h1>New season shoes</h1><div class="grid">${products.map((p) => `
    <div class="card" data-go="/product/${p.slug}">
      <div class="shoe"></div><div>${p.name}</div><div class="price">${money(p.price)}</div>
    </div>`).join("")}</div>`);
}

async function product(slug) {
  const p = await api(`/api/products/${slug}`);
  layout(`<h1>${p.name}</h1><div class="price">${money(p.price)}</div><p>${p.description}</p>
    <div class="sizes">${Object.entries(p.sizes).map(([size, stock]) =>
      `<span class="sz ${stock ? "" : "out"}" data-s="${size}">${size}</span>`).join("")}</div>
    <div class="add">Add to bag</div><div class="msg"></div>`);
  let size = null;
  app.querySelectorAll(".sz:not(.out)").forEach((el) => el.addEventListener("click", () => {
    app.querySelectorAll(".sz").forEach((other) => other.classList.remove("sel"));
    el.classList.add("sel");
    size = el.dataset.s;
  }));
  app.querySelector(".add").addEventListener("click", async () => {
    const msg = app.querySelector(".msg");
    if (!size) { msg.textContent = "Pick a size first."; return; }
    try { await api("/api/cart", { method: "POST", body: JSON.stringify({ slug, size }) }); msg.textContent = "Added to your bag."; }
    catch (error) { msg.textContent = error.message; }
  });
}

async function cart() {
  const { items, total } = await api("/api/cart");
  layout(`<h1>Your bag</h1>${items.length ? items.map((i) => `<p>${i.name} · UK ${i.size} · ${money(i.price)}</p>`).join("") +
    `<p class="price">Total ${money(total)}</p><div class="add" id="checkout">Place order</div><div class="msg"></div>` : "<p>Your bag is empty.</p>"}`);
  const button = document.getElementById("checkout");
  if (button) button.addEventListener("click", async () => {
    try { const order = await api("/api/orders", { method: "POST" }); app.querySelector(".msg").textContent = `Order ${order.id} placed.`; }
    catch (error) { app.querySelector(".msg").textContent = error.message; }
  });
}

function login() {
  layout(`<h1>Sign in</h1><form><label for="email">Email</label><input id="email" type="email" autocomplete="email" />
    <label for="password">Password</label><input id="password" type="password" /><button>Sign in</button><div class="msg"></div></form>`);
  app.querySelector("form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await api("/api/login", { method: "POST", body: JSON.stringify({ email: email.value, password: password.value }) });
      go("/delivery");
    } catch (error) { app.querySelector(".msg").textContent = error.message; }
  });
}

function delivery() {
  layout(`<h1>Check delivery</h1><form><label for="pin">PIN code</label><input id="pin" inputmode="numeric" /><button>Check</button><div class="msg"></div></form>`);
  app.querySelector("form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const msg = app.querySelector(".msg");
    try { const result = await api(`/api/delivery?pin=${encodeURIComponent(pin.value)}`); msg.textContent = `Arrives in ${result.estimate}.`; }
    catch (error) {
      if (error.status === 401) { msg.innerHTML = 'Please <span data-go="/login" style="text-decoration:underline;cursor:pointer">sign in</span> to check delivery.'; msg.querySelector("[data-go]").addEventListener("click", () => go("/login")); }
      else msg.textContent = error.message;
    }
  });
}

async function policies() {
  const data = await api("/api/policies");
  layout(`<h1>Help</h1>${Object.entries(data).map(([key, text]) => `<h3>${key[0].toUpperCase() + key.slice(1)}</h3><p>${text}</p>`).join("")}`);
}

function offer() {
  if (sessionStorage.getItem("ns-offer")) return;
  setTimeout(() => {
    const overlay = document.createElement("div");
    overlay.className = "overlay";
    overlay.innerHTML = `<div class="offer"><div class="x">×</div><h2>10% off your first pair</h2><p>Join the list for early access.</p><input placeholder="Email address" /></div>`;
    overlay.querySelector(".x").addEventListener("click", () => { sessionStorage.setItem("ns-offer", "1"); overlay.remove(); });
    document.body.appendChild(overlay);
  }, 800);
}

async function render() {
  const path = location.pathname;
  try {
    if (path.startsWith("/product/")) await product(decodeURIComponent(path.split("/")[2]));
    else if (path === "/cart") await cart();
    else if (path === "/login") login();
    else if (path === "/delivery") delivery();
    else if (path === "/policies") await policies();
    else await home();
  } catch (error) { layout(`<p>Something went wrong: ${error.message}</p>`); }
}

render();
offer();
