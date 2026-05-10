async function postJson(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Erro ao salvar.");
  }
  return res.json();
}

function initStatusSelectors() {
  if (!window.MT_ESCALAS?.isAdmin) return;
  document.body.addEventListener("change", async (e) => {
    const el = e.target;
    if (!(el instanceof HTMLElement)) return;
    if (!el.matches("[data-status]")) return;

    const scheduleId = parseInt(el.dataset.scheduleId, 10);
    const employeeId = parseInt(el.dataset.employeeId, 10);
    const status = el.value;
    try {
      await postJson("/api/assignment/status", { scheduleId, employeeId, status });
      const card = el.closest(".player-card");
      if (card) {
        card.classList.remove("player-titular", "player-extra", "player-falta", "player-ferias");
        card.classList.add(`player-${status}`);
      }
    } catch (err) {
      el.value = "titular";
    }
  });
}

function initShareModal() {
  const modalEl = document.getElementById("shareModal");
  if (!modalEl) return;

  const shareDownload = document.getElementById("shareDownload");
  const shareWhatsApp = document.getElementById("shareWhatsApp");
  const shareEmail = document.getElementById("shareEmail");
  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);

  document.querySelectorAll("[data-share]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const day = btn.dataset.date;
      const shift = btn.dataset.shift;
      const pdfUrl = `${window.location.origin}/api/pdf?date=${encodeURIComponent(day)}&shift=${encodeURIComponent(shift)}`;
      const msg = `Escala ${shift.toUpperCase()} (${day}) - ManhãesTech Escalas: ${pdfUrl}`;
      shareDownload.href = pdfUrl;
      shareWhatsApp.href = `https://wa.me/?text=${encodeURIComponent(msg)}`;
      shareEmail.href = `mailto:?subject=${encodeURIComponent("Escala de Plantão")}&body=${encodeURIComponent(msg)}`;
      modal.show();
    });
  });
}

function renderLineupCompact(data) {
  const manager = data.manager?.name || "";
  const total = (data.players || []).length;
  const faltas = (data.players || []).filter((p) => p.status === "falta").length;
  const ferias = (data.players || []).filter((p) => p.status === "ferias").length;
  const items = (data.players || []).map((p) => {
    const cls =
      p.status === "extra"
        ? "text-warning"
        : p.status === "falta"
          ? "text-danger"
          : p.status === "ferias"
            ? "text-warning"
            : "text-info";
    return `<div class="d-flex justify-content-between gap-2">
      <div class="text-truncate">${p.employee.name}</div>
      <div class="${cls} small">${p.status}</div>
    </div>`;
  });
  const badges = [
    `<span class="badge text-bg-secondary">${total}/7</span>`,
    faltas ? `<span class="badge text-bg-danger ms-1">Falta: ${faltas}</span>` : "",
    ferias ? `<span class="badge ms-1" style="background:#FF8A00;">Férias: ${ferias}</span>` : "",
  ].join("");

  return `<div class="small text-secondary mb-2 d-flex flex-wrap align-items-center justify-content-between gap-2">
      <div>Encarregado: <span class="text-light">${manager}</span></div>
      <div>${badges}</div>
    </div>
    <div class="d-grid gap-1">${items.join("")}</div>`;
}

let _cachedManagers = null;
let _cachedPorters = null;
let _currentDayIso = null;
let _currentDaySchedules = null;
let _pendingSwap = null;

async function getManagers() {
  if (_cachedManagers) return _cachedManagers;
  const res = await fetch("/api/employees?role=encarregado");
  _cachedManagers = await res.json();
  return _cachedManagers;
}

async function getPorters() {
  if (_cachedPorters) return _cachedPorters;
  const res = await fetch("/api/employees?role=porteiro");
  _cachedPorters = await res.json();
  return _cachedPorters;
}

function onlyExtras(porters) {
  return (porters || []).filter((p) => p.is_extra || p.squad === "Banco de Extras");
}

function avatarHtml(emp, sizeCls) {
  if (emp.photoUrl) {
    return `<img alt="${emp.name}" src="${emp.photoUrl}" />`;
  }
  const initials = (emp.name || "?").slice(0, 2).toUpperCase();
  return `<div class="player-fallback">${initials}</div>`;
}

function swapIconSvg() {
  return `<svg class="swap-icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false">
    <path fill="currentColor" d="M7 7h12a1 1 0 0 0 0-2H7.41l1.3-1.29a1 1 0 1 0-1.42-1.42l-3 3a1 1 0 0 0 0 1.42l3 3a1 1 0 1 0 1.42-1.42L7.41 7Zm10 10H5a1 1 0 1 0 0 2h11.59l-1.3 1.29a1 1 0 1 0 1.42 1.42l3-3a1 1 0 0 0 0-1.42l-3-3a1 1 0 1 0-1.42 1.42L16.59 17Z"/>
  </svg>`;
}

function renderLineupEditable(data, managers) {
  const managerOptions = (managers || [])
    .map((m) => `<option value="${m.id}" ${m.id === data.manager.id ? "selected" : ""}>${m.name}</option>`)
    .join("");

  const players = (data.players || [])
    .map((p) => {
      return `<div class="lineup-edit-row player-card player-${p.status}" data-swap-row data-schedule-id="${data.id}" data-employee-id="${p.employee.id}">
        <div class="lineup-edit-left">
          <div class="player-avatar lineup-edit-avatar">
            ${avatarHtml(p.employee)}
          </div>
          <div class="lineup-edit-name text-truncate">${p.employee.name}</div>
        </div>
        <div class="lineup-edit-actions">
          <select class="form-select form-select-sm form-select-dark lineup-edit-select" data-status data-schedule-id="${data.id}" data-employee-id="${p.employee.id}">
            <option value="titular" ${p.status === "titular" ? "selected" : ""}>Titular</option>
            <option value="extra" ${p.status === "extra" ? "selected" : ""}>Extra</option>
            <option value="falta" ${p.status === "falta" ? "selected" : ""}>Falta</option>
            <option value="ferias" ${p.status === "ferias" ? "selected" : ""}>Férias</option>
          </select>
          <button class="btn btn-sm btn-swap" type="button" data-swap-employee data-schedule-id="${data.id}" data-employee-id="${p.employee.id}" title="Trocar (↔)" aria-label="Trocar (↔)">
            ${swapIconSvg()}
          </button>
          <button class="btn btn-sm btn-outline-light" type="button" data-substitute data-schedule-id="${data.id}" data-employee-id="${p.employee.id}" data-employee-name="${encodeURIComponent(p.employee.name)}">Substituir</button>
          <button class="btn btn-sm btn-outline-danger" type="button" data-remove data-schedule-id="${data.id}" data-employee-id="${p.employee.id}">Remover</button>
        </div>
      </div>`;
    })
    .join("");

  return `<div class="lineup-edit">
    <div class="lineup-edit-manager">
      <div class="player-avatar player-avatar-lg">
        ${avatarHtml(data.manager)}
      </div>
      <div class="flex-grow-1">
        <div class="d-flex align-items-center justify-content-between gap-2 mb-1">
          <div class="small text-secondary">Encarregado</div>
          <button class="btn btn-sm btn-swap" type="button" data-swap-managers title="Trocar encarregados (Diurno ↔ Noturno)" aria-label="Trocar encarregados (Diurno ↔ Noturno)">
            ${swapIconSvg()}
          </button>
        </div>
        <select class="form-select form-select-dark" data-manager data-schedule-id="${data.id}">
          ${managerOptions}
        </select>
      </div>
    </div>
    <div class="lineup-edit-players">
      ${players}
    </div>
  </div>`;
}

async function loadDayModal(dayIso) {
  _currentDayIso = dayIso;
  const titleEl = document.getElementById("dayModalTitle");
  const diurnoEl = document.getElementById("dayDiurno");
  const noturnoEl = document.getElementById("dayNoturno");
  const pdfD = document.getElementById("dayPdfDiurno");
  const pdfN = document.getElementById("dayPdfNoturno");
  const openD = document.getElementById("dayOpenDiurno");
  const openN = document.getElementById("dayOpenNoturno");
  const addD = document.getElementById("dayAddDiurno");
  const addN = document.getElementById("dayAddNoturno");

  titleEl.textContent = `Escala • ${dayIso.split("-").reverse().join("/")}`;
  pdfD.href = `/api/pdf?date=${encodeURIComponent(dayIso)}&shift=diurno`;
  pdfN.href = `/api/pdf?date=${encodeURIComponent(dayIso)}&shift=noturno`;
  openD.href = `/dashboard?date=${encodeURIComponent(dayIso)}`;
  openN.href = `/dashboard?date=${encodeURIComponent(dayIso)}`;

  const isAdmin = !!window.MT_ESCALAS?.isAdmin;
  const [managers, d, n] = await Promise.all([
    isAdmin ? getManagers() : Promise.resolve([]),
    fetch(`/api/schedule?date=${encodeURIComponent(dayIso)}&shift=diurno`).then((r) => r.json()),
    fetch(`/api/schedule?date=${encodeURIComponent(dayIso)}&shift=noturno`).then((r) => r.json()),
  ]);

  _currentDaySchedules = { diurnoId: d.id, noturnoId: n.id };
  _pendingSwap = null;

  diurnoEl.innerHTML = isAdmin ? renderLineupEditable(d, managers) : renderLineupCompact(d);
  noturnoEl.innerHTML = isAdmin ? renderLineupEditable(n, managers) : renderLineupCompact(n);

  if (addD) addD.dataset.scheduleId = String(d.id);
  if (addN) addN.dataset.scheduleId = String(n.id);
}

function initCalendar() {
  if (!window.MT_ESCALAS?.calendar?.enabled) return;

  const el = document.getElementById("calendar");
  if (!el) return;

  const modalEl = document.getElementById("dayModal");
  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);

  const cal = new FullCalendar.Calendar(el, {
    initialView: "dayGridMonth",
    height: "auto",
    headerToolbar: {
      left: "prev,next today",
      center: "title",
      right: "dayGridMonth,timeGridWeek",
    },
    events: "/api/events",
    dateClick: async (info) => {
      await loadDayModal(info.dateStr);
      modal.show();
    },
    eventClick: async (info) => {
      await loadDayModal(info.event.startStr);
      modal.show();
    },
  });
  cal.render();
}

function initManagerSelectors() {
  if (!window.MT_ESCALAS?.isAdmin) return;
  document.body.addEventListener("change", async (e) => {
    const el = e.target;
    if (!(el instanceof HTMLElement)) return;
    if (!el.matches("[data-manager]")) return;

    const scheduleId = parseInt(el.dataset.scheduleId, 10);
    const managerId = parseInt(el.value, 10);
    try {
      await postJson("/api/schedule/manager", { scheduleId, managerId });
    } catch (err) {
    }
  });
}

function initRemoveAndSubstitute() {
  if (!window.MT_ESCALAS?.isAdmin) return;
  const subModalEl = document.getElementById("substituteModal");
  const subSelect = document.getElementById("substituteSelect");
  const subAbsentName = document.getElementById("substituteAbsentName");
  const subConfirm = document.getElementById("substituteConfirm");
  const subModal = subModalEl ? bootstrap.Modal.getOrCreateInstance(subModalEl) : null;

  let pending = null;

  function setPendingSwap(next) {
    const prev = _pendingSwap;
    _pendingSwap = next;
    if (prev) {
      const prevRow = document.querySelector(
        `[data-swap-row][data-schedule-id="${prev.scheduleId}"][data-employee-id="${prev.employeeId}"]`,
      );
      if (prevRow) prevRow.classList.remove("swap-pending");
    }
    if (next) {
      const nextRow = document.querySelector(
        `[data-swap-row][data-schedule-id="${next.scheduleId}"][data-employee-id="${next.employeeId}"]`,
      );
      if (nextRow) nextRow.classList.add("swap-pending");
    }
  }

  document.body.addEventListener("click", async (e) => {
    const target = e.target;
    if (!(target instanceof HTMLElement)) return;
    const el =
      target.closest("[data-remove]") ||
      target.closest("[data-substitute]") ||
      target.closest("[data-swap-employee]") ||
      target.closest("[data-swap-managers]");
    if (!el) return;

    if (el.matches("[data-remove]")) {
      const scheduleId = parseInt(el.dataset.scheduleId, 10);
      const employeeId = parseInt(el.dataset.employeeId, 10);
      try {
        await postJson("/api/assignment/remove", { scheduleId, employeeId });
        if (_currentDayIso) await loadDayModal(_currentDayIso);
      } catch (err) {
      }
      return;
    }

    if (el.matches("[data-swap-managers]")) {
      const scheduleIdA =
        parseInt(el.dataset.scheduleIdA || "0", 10) || _currentDaySchedules?.diurnoId || 0;
      const scheduleIdB =
        parseInt(el.dataset.scheduleIdB || "0", 10) || _currentDaySchedules?.noturnoId || 0;
      if (!scheduleIdA || !scheduleIdB) return;
      try {
        await postJson("/api/schedule/swap-managers", {
          scheduleIdA,
          scheduleIdB,
        });
        if (_currentDayIso) await loadDayModal(_currentDayIso);
        else window.location.reload();
      } catch (err) {
      }
      return;
    }

    if (el.matches("[data-swap-employee]")) {
      const scheduleId = parseInt(el.dataset.scheduleId, 10);
      const employeeId = parseInt(el.dataset.employeeId, 10);

      if (!_pendingSwap) {
        setPendingSwap({ scheduleId, employeeId });
        return;
      }

      if (_pendingSwap.scheduleId === scheduleId && _pendingSwap.employeeId === employeeId) {
        setPendingSwap(null);
        return;
      }

      try {
        await postJson("/api/assignment/swap", {
          scheduleIdA: _pendingSwap.scheduleId,
          employeeIdA: _pendingSwap.employeeId,
          scheduleIdB: scheduleId,
          employeeIdB: employeeId,
        });
        setPendingSwap(null);
        if (_currentDayIso) await loadDayModal(_currentDayIso);
        else window.location.reload();
      } catch (err) {
        setPendingSwap(null);
      }
      return;
    }

    if (el.matches("[data-substitute]")) {
      if (!subModal || !subSelect || !subConfirm || !subAbsentName) return;

      const scheduleId = parseInt(el.dataset.scheduleId, 10);
      const absentEmployeeId = parseInt(el.dataset.employeeId, 10);
      const absentName = decodeURIComponent(el.dataset.employeeName || "");

      const assignedIds = new Set(
        Array.from(document.querySelectorAll(`[data-status][data-schedule-id="${scheduleId}"]`)).map((s) =>
          parseInt(s.dataset.employeeId, 10),
        ),
      );

      const porters = await getPorters();
      const options = onlyExtras(porters)
        .filter((p) => p.id !== absentEmployeeId && !assignedIds.has(p.id))
        .map((p) => `<option value="${p.id}">${p.name}${p.is_extra ? " (Extra)" : ""}</option>`)
        .join("");

      subSelect.innerHTML = options || `<option value="">Nenhum disponível</option>`;
      subSelect.disabled = !options;
      subConfirm.disabled = !options;

      subAbsentName.textContent = absentName || "-";
      pending = { scheduleId, absentEmployeeId };
      subModal.show();
    }
  });

  if (subConfirm) {
    subConfirm.addEventListener("click", async () => {
      if (!pending) return;
      const substituteEmployeeId = parseInt(subSelect.value, 10);
      if (!substituteEmployeeId) return;
      try {
        await postJson("/api/assignment/substitute", {
          scheduleId: pending.scheduleId,
          absentEmployeeId: pending.absentEmployeeId,
          substituteEmployeeId,
        });
        if (_currentDayIso) await loadDayModal(_currentDayIso);
        if (subModal) subModal.hide();
      } catch (err) {
      } finally {
        pending = null;
      }
    });
  }
}

function initAddButtons() {
  if (!window.MT_ESCALAS?.isAdmin) return;
  const addModalEl = document.getElementById("addModal");
  const addSelect = document.getElementById("addSelect");
  const addHint = document.getElementById("addModalHint");
  const addConfirm = document.getElementById("addConfirm");
  const addModal = addModalEl ? bootstrap.Modal.getOrCreateInstance(addModalEl) : null;

  let pending = null;

  function assignedIdsForSchedule(scheduleId) {
    return new Set(
      Array.from(document.querySelectorAll(`[data-status][data-schedule-id="${scheduleId}"]`)).map((s) =>
        parseInt(s.dataset.employeeId, 10),
      ),
    );
  }

  async function openAdd(scheduleId, label) {
    if (!addModal || !addSelect || !addConfirm || !addHint) return;
    const porters = onlyExtras(await getPorters());
    const assigned = assignedIdsForSchedule(scheduleId);
    const options = porters
      .filter((p) => !assigned.has(p.id))
      .map((p) => `<option value="${p.id}">${p.name}${p.is_extra ? " (Extra)" : ""}</option>`)
      .join("");

    addSelect.innerHTML = options || `<option value="">Nenhum disponível</option>`;
    addSelect.disabled = !options;
    addConfirm.disabled = !options;
    addHint.textContent = label;

    pending = { scheduleId };
    addModal.show();
  }

  document.body.addEventListener("click", async (e) => {
    const el = e.target;
    if (!(el instanceof HTMLElement)) return;

    if (el.id === "dayAddDiurno" || el.id === "dayAddNoturno") {
      const scheduleId = parseInt(el.dataset.scheduleId || "0", 10);
      if (!scheduleId) return;
      const label = el.id === "dayAddDiurno" ? "Adicionar no plantão Diurno" : "Adicionar no plantão Noturno";
      await openAdd(scheduleId, label);
    }
  });

  if (addConfirm) {
    addConfirm.addEventListener("click", async () => {
      if (!pending) return;
      const employeeId = parseInt(addSelect.value, 10);
      if (!employeeId) return;
      try {
        await postJson("/api/assignment/add", { scheduleId: pending.scheduleId, employeeId });
        if (_currentDayIso) await loadDayModal(_currentDayIso);
        if (addModal) addModal.hide();
      } catch (err) {
      } finally {
        pending = null;
      }
    });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initStatusSelectors();
  initManagerSelectors();
  initRemoveAndSubstitute();
  initAddButtons();
  initShareModal();
  initCalendar();
});
