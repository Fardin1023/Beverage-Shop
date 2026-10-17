// =============================================================================
// Daily Drop Beverage Shop - Role-Based Access Control (RBAC) Engine
// Roles: customer | shopkeeper | supplier | company
// =============================================================================

const _prefix = window.location.port === '8000' ? '/static' : '';

const ROLES = {
  customer: {
    id: 'customer',
    name: 'Customer',
    icon: '👤',
    pageUrl: `${_prefix}/customer/index.html`,
    desc: 'Browse drinks, secret drops, and punch card loyalty'
  },
  shopkeeper: {
    id: 'shopkeeper',
    name: 'Shopkeeper',
    icon: '🧑‍🍳',
    pageUrl: `${_prefix}/counter/index.html`,
    desc: 'View products stocks and product demand sales graph'
  },
  supplier: {
    id: 'supplier',
    name: 'Supplier',
    icon: '🚚',
    pageUrl: `${_prefix}/supplier/index.html`,
    desc: 'Access shopkeeper stock DB, deliver stock, requisition from company'
  },
  company: {
    id: 'company',
    name: 'Company Admin',
    icon: '🏢',
    pageUrl: `${_prefix}/index.html`,
    desc: 'Access suppliers database, approve/reject stock requests'
  }
};

function getActiveRole() {
  const saved = localStorage.getItem('daily_drop_role');
  if (saved && ROLES[saved]) {
    return saved;
  }
  return 'company'; // Default to company for administrative testing
}

function setActiveRole(roleId) {
  if (ROLES[roleId]) {
    localStorage.setItem('daily_drop_role', roleId);
    window.location.href = ROLES[roleId].pageUrl;
  }
}

function initRBAC(currentPageRole) {
  // If not explicitly set in storage, adopt the page's role
  let currentRole = localStorage.getItem('daily_drop_role');
  if (!currentRole || !ROLES[currentRole]) {
    currentRole = currentPageRole;
    localStorage.setItem('daily_drop_role', currentRole);
  }

  // Inject Role Switcher and Access Enforcement
  renderRoleSwitcher(currentRole, currentPageRole);
  enforcePageAccess(currentRole, currentPageRole);
}

function renderRoleSwitcher(activeRoleId, currentPageRole) {
  // Check if a role banner container exists, otherwise inject below header or prepend to body
  let banner = document.getElementById('rbac-banner');
  if (!banner) {
    banner = document.createElement('div');
    banner.id = 'rbac-banner';
    banner.className = 'rbac-banner';
    
    const header = document.querySelector('header');
    if (header && header.nextSibling) {
      header.parentNode.insertBefore(banner, header.nextSibling);
    } else {
      document.body.insertBefore(banner, document.body.firstChild);
    }
  }

  const roleList = Object.values(ROLES);

  banner.innerHTML = `
    <div class="rbac-container">
      <div class="rbac-left">
        <span class="rbac-shield">🛡️ RBAC System:</span>
        <span class="rbac-current-label">Current Role:</span>
        <span class="rbac-role-pill active-role-${activeRoleId}">
          ${ROLES[activeRoleId].icon} ${ROLES[activeRoleId].name}
        </span>
      </div>
      <div class="rbac-right">
        <span class="rbac-switch-label">Switch Role:</span>
        <div class="rbac-buttons">
          ${roleList.map(r => `
            <button class="rbac-btn ${r.id === activeRoleId ? 'active' : ''}" 
                    title="${r.desc}"
                    onclick="setActiveRole('${r.id}')">
              ${r.icon} ${r.name}
            </button>
          `).join('')}
        </div>
      </div>
    </div>
  `;
}

function enforcePageAccess(activeRoleId, currentPageRole) {
  // Customer can ONLY see the customer products page
  if (activeRoleId === 'customer' && currentPageRole !== 'customer') {
    renderAccessDenied('Customer', 'the Products Page');
    return;
  }

  // Shopkeeper can ONLY see the shopkeeper counter/demand page
  if (activeRoleId === 'shopkeeper' && currentPageRole !== 'shopkeeper') {
    renderAccessDenied('Shopkeeper', "the Products Stocks & Sales Demand page");
    return;
  }

  // Supplier can ONLY access the supplier portal
  if (activeRoleId === 'supplier' && currentPageRole !== 'supplier') {
    renderAccessDenied('Supplier', "the Shopkeeper's Stock Database & Supplier Portal");
    return;
  }

  // Company can access Company Admin Hub and Live DB
  if (activeRoleId === 'company' && (currentPageRole !== 'company' && currentPageRole !== 'db_viewer')) {
    // Allowed on company page or can navigate
  }
}

function renderAccessDenied(roleName, allowedAreaDescription) {
  const container = document.querySelector('.container') || document.querySelector('.store-container') || document.body;
  
  // Hide actual contents
  const originalContents = Array.from(document.body.children).filter(el => 
    el.tagName !== 'HEADER' && el.id !== 'rbac-banner' && el.id !== 'toast'
  );
  originalContents.forEach(el => el.style.display = 'none');

  const barrier = document.createElement('div');
  barrier.className = 'access-denied-box';
  barrier.innerHTML = `
    <div class="access-denied-icon">🔒</div>
    <h2>Role-Based Access Restricted</h2>
    <p>
      Your current active role is <strong>${roleName}</strong>.
      According to the security policy, a <strong>${roleName}</strong> is only permitted to access <strong>${allowedAreaDescription}</strong>.
    </p>
    <div class="access-denied-actions">
      <button class="btn btn-primary" onclick="window.location.href='${ROLES[getActiveRole()].pageUrl}'">
        &larr; Go to ${ROLES[getActiveRole()].name} Permitted View
      </button>
      <div style="margin-top: 12px; font-size: 0.85rem; color: #94a3b8;">
        Or select a different role using the top RBAC switcher bar.
      </div>
    </div>
  `;

  document.body.appendChild(barrier);
}
