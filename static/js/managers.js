function isCurrentUserStaffOrManager() {
  try {
    const userData = JSON.parse(localStorage.getItem("user_data") || "{}");
    if (userData.user_type === "manager" || userData.user_type === "staff")
      return true;
    if (
      userData.manager_account &&
      Object.keys(userData.manager_account).length > 0
    )
      return true;
    if (
      userData.staff_account &&
      Object.keys(userData.staff_account).length > 0
    )
      return true;
  } catch (e) {}
  return false;
}

window.openManagerModal = function (id = null) {
  if (isCurrentUserStaffOrManager()) {
    showToast(
      "Access Denied",
      "Only business owners can add or edit managers.",
      "error",
    );
    return;
  }
  const modal = document.getElementById("manager-modal");
  if (!modal) return;

  // reset form
  document.getElementById("manager-modal-id").value = id || "";
  document.getElementById("m-fullname").value = "";
  document.getElementById("m-email").value = "";
  document.getElementById("m-department").value = "";
  document.getElementById("m-jobtitle").value = "";
  document.getElementById("m-add-stock").checked = false;
  document.getElementById("m-edit-stock").checked = false;
  document.getElementById("m-add-cashier").checked = false;
  document.getElementById("m-edit-cashier").checked = false;
  document.getElementById("m-manage-online-store").checked = false;
  document.getElementById("m-manage-payroll").checked = false;
  if (document.getElementById("m-manage-finances"))
    document.getElementById("m-manage-finances").checked = false;

  const titleEl = document.getElementById("manager-modal-title");
  const subtitleEl = document.getElementById("manager-modal-subtitle");
  const btn = document.getElementById("submit-manager-btn");
  if (btn) btn.disabled = false;

  if (typeof window.populateDepartments === "function") {
    window.populateDepartments("m-department");
  }

  if (id) {
    titleEl.innerText = "Edit Manager";
    subtitleEl.innerText = "Update administrative access for personnel";
    btn.innerText = "Update Manager";

    // fetch details
    apiFetch(`/api/user/manager/${id}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.status && data.data) {
          const m = data.data;
          document.getElementById("m-fullname").value = m.manager_name || "";
          document.getElementById("m-email").value = m.manager_email || "";

          // Set department after a slight delay to ensure it's populated
          setTimeout(() => {
            document.getElementById("m-department").value =
              m.manager_department || "";
          }, 500);

          document.getElementById("m-jobtitle").value = m.job_title || "";
          document.getElementById("m-add-stock").checked = !!m.add_stock;
          document.getElementById("m-edit-stock").checked = !!m.edit_stock;
          document.getElementById("m-add-cashier").checked = !!m.add_cashier;
          document.getElementById("m-edit-cashier").checked = !!m.edit_cashier;
          document.getElementById("m-manage-online-store").checked =
            !!m.manage_online_store;
          document.getElementById("m-manage-payroll").checked =
            !!m.manage_payroll;
          if (document.getElementById("m-manage-finances"))
            document.getElementById("m-manage-finances").checked =
              !!m.manage_finances;
        }
      });
  } else {
    titleEl.innerText = "New Manager";
    subtitleEl.innerText = "Create administrative access for personnel";
    btn.innerText = "Create Manager";
  }

  modal.classList.add("show");
};

window.closeManagerModal = function () {
  const modal = document.getElementById("manager-modal");
  if (modal) modal.classList.remove("show");
};

window.handleSubmitManager = function () {
  if (isCurrentUserStaffOrManager()) {
    showToast(
      "Access Denied",
      "Only business owners can add or edit managers.",
      "error",
    );
    return;
  }
  const id = document.getElementById("manager-modal-id").value;

  const name = document.getElementById("m-fullname").value;
  const email = document.getElementById("m-email").value;
  const department = document.getElementById("m-department").value;
  const jobTitle = document.getElementById("m-jobtitle").value;

  const addStock = document.getElementById("m-add-stock").checked;
  const editStock = document.getElementById("m-edit-stock").checked;
  const addCashier = document.getElementById("m-add-cashier").checked;
  const editCashier = document.getElementById("m-edit-cashier").checked;
  const manageOnlineStore = document.getElementById(
    "m-manage-online-store",
  ).checked;
  const managePayroll = document.getElementById("m-manage-payroll").checked;
  const manageFinances =
    document.getElementById("m-manage-finances")?.checked || false;

  if (!name || !email || !department) {
    showToast(
      "Missing Information",
      "Please fill in name, email and department.",
      "error",
    );
    return;
  }

  const btn = document.getElementById("submit-manager-btn");
  const originalText = btn.innerText;
  btn.disabled = true;
  btn.innerHTML =
    '<div class="inline-block animate-spin rounded-full h-4 w-4 border-2 border-bg-dark border-t-transparent mr-2"></div> Saving...';

  const payload = {
    manager_name: name,
    manager_email: email,
    manager_department: department,
    job_title: jobTitle,
    add_stock: addStock,
    edit_stock: editStock,
    add_cashier: addCashier,
    edit_cashier: editCashier,
    manage_online_store: manageOnlineStore,
    manage_payroll: managePayroll,
    manage_finances: manageFinances,
  };

  const url = id ? `/api/user/manager/${id}` : "/api/user/manager";
  const method = id ? "PATCH" : "POST";

  apiFetch(url, {
    method: method,
    body: JSON.stringify(payload),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status) {
        window.closeManagerModal();
        showToast(
          "Success",
          id
            ? "Manager details updated successfully"
            : "Manager created successfully",
          "success",
        );
        if (typeof window.initManagers === "function") window.initManagers();
        btn.disabled = false;
        btn.innerText = originalText;
      } else {
        showToast("Error", data.message || "Failed to save manager", "error");
        btn.disabled = false;
        btn.innerText = originalText;
      }
    })
    .catch((err) => {
      console.error("Save manager error:", err);
      showToast("System Error", "An unexpected error occurred.", "error");
      btn.disabled = false;
      btn.innerText = originalText;
    });
};

// Global initialization for managers view
window.initManagers = () => {
  if (!document.getElementById("managers-tbody")) return;

  const isRestricted = isCurrentUserStaffOrManager();
  const newManagerBtns = document.querySelectorAll(
    'button[onclick*="openManagerModal"]',
  );
  newManagerBtns.forEach((btn) => {
    if (isRestricted) {
      btn.classList.add("hidden");
    } else {
      btn.classList.remove("hidden");
    }
  });

  if (typeof initPaginatedTable === "function") {
    initPaginatedTable({
      endpoint: "/api/managers/filter",
      containerId: "managers-tbody",
      prevBtnId: "managers-prev-btn",
      nextBtnId: "managers-next-btn",
      infoId: "managers-pagination-info",
      searchId: "managers-filter-search",
      renderRow: (m) => {
        const permissions = [];
        if (m.add_stock) permissions.push("Add Stock");
        if (m.edit_stock) permissions.push("Edit Stock");
        if (m.add_cashier) permissions.push("Add Cashier");
        if (m.edit_cashier) permissions.push("Edit Cashier");
        if (m.manage_online_store) permissions.push("Online Store");
        if (m.manage_payroll) permissions.push("Payroll");
        if (m.manage_finances) permissions.push("Finances");

        const permissionsHtml =
          permissions.length > 0
            ? permissions
                .map(
                  (p) =>
                    `<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-primary/10 text-primary border border-primary/20 mr-1 mb-1 uppercase tracking-tighter">${p}</span>`,
                )
                .join("")
            : '<span class="text-[10px] text-slate-600 font-bold uppercase tracking-tighter">View Only</span>';

        const actionsHtml = isRestricted
          ? '<span class="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Protected</span>'
          : `
                        <div class="flex items-center justify-end gap-2">
                            <button onclick="window.openManagerModal('${m.uniq_id}')" class="p-2 text-slate-500 hover:text-primary hover:bg-primary/10 rounded-lg transition-all" title="Edit Manager">
                                <i data-lucide="edit-2" class="w-4 h-4"></i>
                            </button>
                            <button onclick="handleDeleteManager('${m.uniq_id}')" class="p-2 text-slate-500 hover:text-rose-500 hover:bg-rose-500/10 rounded-lg transition-all" title="Remove Manager">
                                <i data-lucide="trash-2" class="w-4 h-4"></i>
                            </button>
                        </div>
                    `;

        return `
                    <tr class="group hover:bg-white/[0.02] transition-all">
                        <td class="px-6 py-5">
                            <div class="flex items-center gap-4">
                                <div class="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center text-slate-400 group-hover:text-primary transition-all overflow-hidden border border-white/5 group-hover:border-primary/20">
                                    ${m.image ? `<img src="${m.image}" class="w-full h-full object-cover">` : `<i data-lucide="user" class="w-5 h-5"></i>`}
                                </div>
                                <div>
                                    <p class="text-sm font-bold text-white group-hover:text-primary transition-colors">${m.manager_name}</p>
                                    <p class="text-[10px] text-slate-500 uppercase tracking-widest mt-0.5">${m.manager_email}</p>
                                </div>
                            </div>
                        </td>
                        <td class="px-6 py-5">
                            <p class="text-xs font-bold text-slate-400">${m.manager_department}</p>
                            <p class="text-[10px] text-slate-500 font-medium mt-0.5">${m.job_title || "No Title"}</p>
                        </td>
                        <td class="px-6 py-5">
                            <div class="flex flex-wrap max-w-xs">
                                ${permissionsHtml}
                            </div>
                        </td>
                        <td class="px-6 py-5 text-right">
                            ${actionsHtml}
                        </td>
                    </tr>
                `;
      },
    });
  }
};

function handleDeleteManager(id) {
  if (isCurrentUserStaffOrManager()) {
    showToast(
      "Access Denied",
      "Managers cannot delete manager accounts.",
      "error",
    );
    return;
  }
  const isLight = document.documentElement.classList.contains("light");
  Swal.fire({
    title: "Remove Manager?",
    text: "This action will permanently revoke their administrative access.",
    icon: "warning",
    showCancelButton: true,
    confirmButtonColor: "#ef4444",
    cancelButtonColor: isLight ? "#94a3b8" : "rgba(255,255,255,0.05)",
    confirmButtonText: "Yes, Remove Access",
    background: isLight ? "#ffffff" : "hsl(220, 15%, 8%)",
    color: isLight ? "#0f172a" : "#fff",
  }).then((result) => {
    if (result.isConfirmed) {
      apiFetch(`/api/user/manager/${id}`, {
        method: "DELETE",
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.status) {
            showToast(
              "Access Revoked",
              "The manager has been removed from the system.",
              "success",
            );
            if (typeof window.initManagers === "function")
              window.initManagers();
          } else {
            showToast(
              "Error",
              data.message || "Failed to remove manager",
              "error",
            );
          }
        })
        .catch((err) => {
          console.error("Delete manager error:", err);
          showToast("System Error", "Unable to complete request.", "error");
        });
    }
  });
}
