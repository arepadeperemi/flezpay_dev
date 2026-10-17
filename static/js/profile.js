/**
 * profile.js - Profile Page Management
 */

window.initProfilePage = initProfilePage;

let _profileInitializing = false;

async function initProfilePage() {
  if (!document.getElementById("save-profile")) return;
  if (_profileInitializing) return;
  _profileInitializing = true;

  bindEvents();
  await loadProfileData();

  _profileInitializing = false;
}

function bindEvents() {
  const saveBtn = document.getElementById("save-profile");
  if (saveBtn) {
    saveBtn.addEventListener("click", async () => {
      saveBtn.disabled = true;
      saveBtn.innerHTML =
        '<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Saving...';
      if (typeof lucide !== "undefined") lucide.createIcons();

      const success = await saveProfile();

      if (success) {
        Swal.fire({
          icon: "success",
          title: "Saved",
          text: "Profile updated successfully.",
          background: "#1e293b",
          color: "#fff",
          confirmButtonColor: "#cfff45",
        });
      } else {
        Swal.fire({
          icon: "error",
          title: "Error",
          text: "Failed to update profile.",
          background: "#1e293b",
          color: "#fff",
          confirmButtonColor: "#cfff45",
        });
      }

      saveBtn.disabled = false;
      saveBtn.innerHTML =
        '<i data-lucide="save" class="w-4 h-4"></i> Save Changes';
      if (typeof lucide !== "undefined") lucide.createIcons();
    });
  }

  // Avatar Upload
  const avatarBtn = document.getElementById("avatar-upload-btn");
  const avatarInput = document.getElementById("avatar-upload-input");
  if (avatarBtn && avatarInput) {
    avatarBtn.addEventListener("click", () => avatarInput.click());
    avatarInput.addEventListener("change", async (e) => {
      if (e.target.files && e.target.files[0]) {
        const file = e.target.files[0];
        if (file.size > 2 * 1024 * 1024) {
          Swal.fire("Error", "Image must be under 2MB", "error");
          e.target.value = "";
          return;
        }
        handleImagePreview(e, "#avatar-preview-container");

        // Auto-save the avatar instantly upon selection
        const saveBtn = document.getElementById("save-profile");
        if (saveBtn) saveBtn.click();
      }
    });
  }

  // Change Email
  const changeEmailBtn = document.getElementById("change-email-btn");
  if (changeEmailBtn && !changeEmailBtn.dataset.listenerAttached) {
    changeEmailBtn.dataset.listenerAttached = "true";
    changeEmailBtn.addEventListener("click", handleProfileChangeEmail);
  }
}

async function handleProfileChangeEmail() {
  const { value: newEmail } = await Swal.fire({
    title: "Change Email Address",
    input: "email",
    inputLabel: "Enter your new email address",
    inputPlaceholder: "e.g., james@example.com",
    showCancelButton: true,
    confirmButtonText: "Send OTP",
    confirmButtonColor: "#cfff45",
    background: "#1e293b",
    color: "#fff",
    showLoaderOnConfirm: true,
    preConfirm: async (email) => {
      try {
        const res = await apiFetch(
          `${window.FLEZ_API_BASE || ""}/api/user/validateEmail`,
          {
            method: "POST",
            body: JSON.stringify({ user_email: email }),
          },
        );
        const data = await res.json();
        if (!data.status) throw new Error(data.message || "Failed to send OTP");
        return email;
      } catch (error) {
        Swal.showValidationMessage(`Request failed: ${error}`);
      }
    },
    allowOutsideClick: () => !Swal.isLoading(),
  });

  if (!newEmail) return;

  const { value: otp } = await Swal.fire({
    title: "Verify New Email",
    text: `Enter the OTP sent to ${newEmail}`,
    input: "text",
    inputPlaceholder: "Enter 4-digit PIN",
    showCancelButton: true,
    confirmButtonText: "Verify & Update",
    confirmButtonColor: "#cfff45",
    background: "#1e293b",
    color: "#fff",
    showLoaderOnConfirm: true,
    preConfirm: async (pin) => {
      try {
        const res = await apiFetch(
          `${window.FLEZ_API_BASE || ""}/api/user/validateEmail/update`,
          {
            method: "PATCH",
            body: JSON.stringify({ user_email: newEmail, user_pin: pin }),
          },
        );
        const data = await res.json();
        if (!data.status) throw new Error(data.message || "Invalid OTP");
        return data;
      } catch (error) {
        Swal.showValidationMessage(`Verification failed: ${error}`);
      }
    },
    allowOutsideClick: () => !Swal.isLoading(),
  });

  if (otp) {
    const emailInput = document.getElementById("profile-email");
    if (emailInput) emailInput.value = newEmail;
    Swal.fire({
      title: "Success",
      text: "Your email has been updated successfully.",
      icon: "success",
      background: "#1e293b",
      color: "#fff",
      confirmButtonColor: "#cfff45",
    });
  }
}

async function loadProfileData() {
  const skeleton = document.getElementById("profile-skeleton");
  const content = document.getElementById("profile-content-container");

  // Pre-fill immediately from local cache if present to avoid blank/pulsing delay
  try {
    const cached = JSON.parse(localStorage.getItem("user_data") || "null");
    if (cached) {
      window.userData = cached;
      populateProfile(cached);
      if (skeleton) skeleton.classList.add("hidden");
      if (content) content.classList.remove("hidden");
    }
  } catch (e) {
    console.warn("Cached user data parse failed in profile:", e);
  }

  try {
    const response = await apiFetch(
      `${window.FLEZ_API_BASE || ""}/api/user/data`,
      { method: "POST" },
    );
    if (response.status === 401 || response.status === 403) {
      window.location.href = "/login";
      return;
    }
    const resJson = await response.json();
    if (resJson.status && resJson.data) {
      window.userData = resJson.data;
      localStorage.setItem("user_data", JSON.stringify(resJson.data));
      populateProfile(resJson.data);
      if (skeleton) skeleton.classList.add("hidden");
      if (content) content.classList.remove("hidden");
    } else {
      console.error("Failed to load profile data");
    }
  } catch (err) {
    console.error("Error loading profile:", err);
  } finally {
    if (skeleton) skeleton.classList.add("hidden");
    if (content) content.classList.remove("hidden");
    if (window.lucide) window.lucide.createIcons();
  }
}

function setInputValue(id, val) {
  const el = document.getElementById(id);
  if (el) el.value = val || "";
}

function populateProfile(data) {
  const isManager =
    data.manager_account && Object.keys(data.manager_account).length > 0;
  const isStaff =
    data.staff_account && Object.keys(data.staff_account).length > 0;
  const details =
    data.details && data.details.length > 0 ? data.details[0] : {};
  const business =
    data.business_details && data.business_details.length > 0
      ? data.business_details[0]
      : {};

  let firstName = details.first_name || "";
  let lastName = details.last_name || "";
  let fullName = [firstName, lastName].filter(Boolean).join(" ");
  let email = data.user_email || "";
  let phone = data.user_phone || "";
  let userType = `${business.plan_code > 0 ? "Business Owner" : "Individual User"}`;

  if (isManager) {
    const m = data.manager_account;
    if (m.manager_name) {
      fullName = m.manager_name;
      const parts = m.manager_name.trim().split(" ");
      firstName = parts[0] || "";
      lastName = parts.slice(1).join(" ") || "";
    }
    if (m.manager_email) email = m.manager_email;
    if (m.phone) phone = m.phone;
    userType = m.job_title ? `${m.job_title} (Manager)` : "Store Manager";
  } else if (isStaff) {
    const s = data.staff_account;
    if (s.staff_name) {
      fullName = s.staff_name;
      const parts = s.staff_name.trim().split(" ");
      firstName = parts[0] || "";
      lastName = parts.slice(1).join(" ") || "";
    }
    if (s.staff_email) email = s.staff_email;
    if (s.phone_number) phone = s.phone_number;
    userType = s.designation ? `${s.designation} (Staff)` : "Staff Member";
  }

  setInputValue("profile-first-name", firstName);
  setInputValue("profile-last-name", lastName);
  setInputValue("profile-full-name", fullName);
  setInputValue("profile-email", email);
  setInputValue("profile-phone", phone);
  setInputValue(
    "profile-category",
    (isManager
      ? data.manager_account.manager_department
      : isStaff
        ? data.staff_account.department
        : business.business_type) || "Retail & Supermarket",
  );

  const displayName = document.getElementById("display-full-name");
  if (displayName && fullName) {
    displayName.textContent = fullName;
  }

  const displayType = document.getElementById("display-user-type");
  if (displayType) {
    displayType.textContent = userType;
  }

  // Update avatar preview using header avatar display logic
  const avatarContainer = document.getElementById("avatar-preview-container");
  if (avatarContainer) {
    let avatarUrl = "";
    let initials = "U";

    if (isManager) {
      const m = data.manager_account;
      avatarUrl = m.image || m.avatar || "";
      if (m.manager_name) {
        const parts = m.manager_name.trim().split(" ");
        initials = (((parts[0]?.[0] || "") + (parts[1]?.[0] || "")) || "M").toUpperCase();
      } else if (window.USER_INITIALS) {
        initials = window.USER_INITIALS;
      }
    } else if (isStaff) {
      const s = data.staff_account;
      avatarUrl = s.image || s.avatar || "";
      if (s.staff_name) {
        const parts = s.staff_name.trim().split(" ");
        initials = (((parts[0]?.[0] || "") + (parts[1]?.[0] || "")) || "S").toUpperCase();
      } else if (window.USER_INITIALS) {
        initials = window.USER_INITIALS;
      }
    } else {
      avatarUrl = details.user_avatar || window.USER_AVATAR_URL || "";
      if (details.first_name && details.last_name) {
        initials = (details.first_name[0] + details.last_name[0]).toUpperCase();
      } else if (window.USER_INITIALS) {
        initials = window.USER_INITIALS;
      }
    }

    if (avatarUrl) {
      avatarContainer.innerHTML = `<img src="${avatarUrl}" alt="User Avatar" class="w-full h-full object-cover" />`;
      avatarContainer.classList.add("overflow-hidden", "p-0");
      avatarContainer.classList.remove(
        "font-bold",
        "font-display",
        "text-primary",
      );
    } else {
      avatarContainer.textContent = initials;
      avatarContainer.classList.remove("overflow-hidden", "p-0");
      avatarContainer.classList.add(
        "font-bold",
        "font-display",
        "text-primary",
      );
    }
  }
}

async function saveProfile() {
  const avatarInput = document.getElementById("avatar-upload-input");

  if (!avatarInput || !avatarInput.files || !avatarInput.files[0]) {
    Swal.fire({
      icon: "info",
      title: "Profile Locked",
      text: "Profile details cannot be edited. Tap the camera icon on your photo to upload a new profile picture.",
      background: "#1e293b",
      color: "#fff",
      confirmButtonColor: "#cfff45",
    });
    return false;
  }

  const formData = new FormData();
  formData.append("user_avatar", avatarInput.files[0]);

  try {
    const res = await apiFetch(
      `${window.FLEZ_API_BASE || ""}/api/user/update/details`,
      {
        method: "PATCH",
        body: formData,
      },
    );

    if (res.ok) {
      // Refresh global avatar by calling loadProfileData again
      await loadProfileData();
      const isManager =
        window.userData.manager_account &&
        Object.keys(window.userData.manager_account).length > 0;
      const isStaff =
        window.userData.staff_account &&
        Object.keys(window.userData.staff_account).length > 0;
      const details =
        window.userData.details && window.userData.details.length > 0
          ? window.userData.details[0]
          : {};
      const newAvatar = isManager
        ? window.userData.manager_account.image ||
          window.userData.manager_account.avatar ||
          ""
        : isStaff
          ? window.userData.staff_account.image ||
            window.userData.staff_account.avatar ||
            ""
          : details.user_avatar || "";
      if (newAvatar) {
        window.USER_AVATAR_URL = newAvatar;
        // Trigger header re-render for avatar
        if (typeof HeaderComponent !== "undefined" && HeaderComponent.init)
          HeaderComponent.init();
      }
      return true;
    }
    return false;
  } catch (err) {
    console.error("Profile save error:", err);
    return false;
  }
}

function handleImagePreview(event, containerSelector) {
  const file = event.target.files[0];
  const container = document.querySelector(containerSelector);
  if (!file || !container) return;

  const reader = new FileReader();
  reader.onload = function (e) {
    container.innerHTML = `<img src="${e.target.result}" class="w-full h-full object-cover" />`;
  };
  reader.readAsDataURL(file);
}

// Auto-run if profile container is present on direct page load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('profile-content-container') || document.getElementById('save-profile')) {
      initProfilePage();
    }
  });
} else {
  if (document.getElementById('profile-content-container') || document.getElementById('save-profile')) {
    initProfilePage();
  }
}

