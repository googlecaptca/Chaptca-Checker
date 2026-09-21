const tabs = document.querySelectorAll('.tab');
const panels = document.querySelectorAll('.form-panel');
const authMessage = document.getElementById('authMessage');

const switchTab = (targetId) => {
  tabs.forEach((tab) => {
    const isActive = tab.dataset.tab === targetId;
    tab.classList.toggle('active', isActive);
  });

  panels.forEach((panel) => {
    panel.classList.toggle('active', panel.id === targetId);
  });
};

tabs.forEach((tab) => {
  tab.addEventListener('click', () => switchTab(tab.dataset.tab));
});

const setAuthMessage = (message, type = 'success') => {
  authMessage.textContent = message;
  authMessage.className = `auth-message ${type}`;
};

const loginForm = document.getElementById('loginForm');
const registerForm = document.getElementById('registerForm');

loginForm.addEventListener('submit', (event) => {
  event.preventDefault();

  const username = document.getElementById('loginUsername').value.trim();
  const password = document.getElementById('loginPassword').value.trim();

  if (!username || !password) {
    setAuthMessage('Username dan password wajib diisi.', 'error');
    return;
  }

  const storageKey = 'chaptca-demo-users';
  const users = JSON.parse(localStorage.getItem(storageKey) || '[]');
  const matchedUser = users.find((user) => user.username === username && user.password === password);

  if (matchedUser) {
    setAuthMessage(`Selamat datang, ${matchedUser.username}! Login berhasil.`, 'success');
    loginForm.reset();
  } else {
    setAuthMessage('Akun tidak ditemukan. Silakan daftar terlebih dahulu.', 'error');
  }
});

registerForm.addEventListener('submit', (event) => {
  event.preventDefault();

  const username = document.getElementById('registerUsername').value.trim();
  const password = document.getElementById('registerPassword').value.trim();

  if (!username || !password) {
    setAuthMessage('Username dan password wajib diisi.', 'error');
    return;
  }

  const storageKey = 'chaptca-demo-users';
  const users = JSON.parse(localStorage.getItem(storageKey) || '[]');

  if (users.some((user) => user.username === username)) {
    setAuthMessage('Username sudah terdaftar. Coba username lain.', 'error');
    return;
  }

  users.push({ username, password });
  localStorage.setItem(storageKey, JSON.stringify(users));

  setAuthMessage(`Akun ${username} berhasil dibuat.`, 'success');
  registerForm.reset();
  switchTab('login-form');
});

const checkerForm = document.getElementById('checkerForm');
const checkerResult = document.getElementById('checkerResult');

checkerForm.addEventListener('submit', (event) => {
  event.preventDefault();

  const email = document.getElementById('emailInput').value.trim();
  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  if (!email) {
    checkerResult.textContent = 'Email harus diisi.';
    checkerResult.className = 'checker-result error';
    return;
  }

  if (!emailPattern.test(email)) {
    checkerResult.textContent = 'Format email tidak valid. Contoh: nama@email.com';
    checkerResult.className = 'checker-result error';
    return;
  }

  const domain = email.split('@')[1].toLowerCase();
  const blockedDomains = ['tempmail.com', 'mailinator.com', '10minutemail.com'];

  if (blockedDomains.includes(domain)) {
    checkerResult.textContent = `Email ${email} terdeteksi sebagai domain sementara dan tidak layak diproses.`;
    checkerResult.className = 'checker-result error';
    return;
  }

  if (domain.endsWith('gmail.com') || domain.endsWith('yahoo.com') || domain.endsWith('outlook.com')) {
    checkerResult.textContent = `Email ${email} tampak valid secara format dan domain umum. Status: aman untuk pengecekan demo.`;
    checkerResult.className = 'checker-result ok';
    return;
  }

  checkerResult.textContent = `Email ${email} valid secara format. Domain ${domain} perlu verifikasi tambahan.`;
  checkerResult.className = 'checker-result warn';
});
