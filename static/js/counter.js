/**
 * CinePay Multiplex Counter POS - Terminal Controller
 * Manages reactive real-time calculations, seat capacity locks,
 * offer layering, and thermal receipt generation.
 */

// Application State
let appState = {
    shows: [],
    selectedShowId: null,
    selectedQuantities: {
        Silver: 0,
        Gold: 0,
        Recliner: 0
    },
    selectedSeatIds: [],
    offers: {
        enableFestival: false,
        enableMember: false,
        memberId: "CINE-VIP"
    },
    latestPricing: null,
    isCalculating: false
};


// DOM Elements
const showsListEl = document.getElementById("showsList");
const tiersContainerEl = document.getElementById("tiersContainer");
const toggleFestivalEl = document.getElementById("toggleFestival");
const toggleMemberEl = document.getElementById("toggleMember");
const memberIdGroupEl = document.getElementById("memberIdGroup");
const memberIdInputEl = document.getElementById("memberIdInput");
const btnQuickMember = document.getElementById("btnQuickMember");
const lineItemsContainerEl = document.getElementById("lineItemsContainer");

// Summary Elements
const summaryGrossEl = document.getElementById("summaryGross");
const summaryDiscountRowEl = document.getElementById("summaryDiscountRow");
const summaryDiscountEl = document.getElementById("summaryDiscount");
const summaryNetTicketsEl = document.getElementById("summaryNetTickets");
const summaryFeeEl = document.getElementById("summaryFee");
const summaryTotalTaxEl = document.getElementById("summaryTotalTax");
const summaryCgstTicketsEl = document.getElementById("summaryCgstTickets");
const summarySgstTicketsEl = document.getElementById("summarySgstTickets");
const summaryCgstFeeEl = document.getElementById("summaryCgstFee");
const summarySgstFeeEl = document.getElementById("summarySgstFee");
const summaryGrandTotalEl = document.getElementById("summaryGrandTotal");
const calculationAuditNotesEl = document.getElementById("calculationAuditNotes");
const billMovieTitleEl = document.getElementById("billMovieTitle");
const billScreenTimeEl = document.getElementById("billScreenTime");
const billTicketCountBadgeEl = document.getElementById("billTicketCountBadge");
const activeShowBadgeEl = document.getElementById("activeShowBadge");

// Buttons & Modals
const btnBookEl = document.getElementById("btnBook");
const btnClearEl = document.getElementById("btnClear");
const btnResetEl = document.getElementById("btnReset");
const btnHistoryEl = document.getElementById("btnHistory");
const btnRulesEl = document.getElementById("btnRules");

const receiptModal = document.getElementById("receiptModal");
const btnCloseModal = document.getElementById("btnCloseModal");
const btnDismissReceipt = document.getElementById("btnDismissReceipt");
const btnPrintReceipt = document.getElementById("btnPrintReceipt");
const thermalReceiptContent = document.getElementById("thermalReceiptContent");

const historyModal = document.getElementById("historyModal");
const btnCloseHistoryModal = document.getElementById("btnCloseHistoryModal");
const historyContainer = document.getElementById("historyContainer");

const rulesModal = document.getElementById("rulesModal");
const btnCloseRulesModal = document.getElementById("btnCloseRulesModal");

const customerNameEl = document.getElementById("customerName");
const customerPhoneEl = document.getElementById("customerPhone");
const paymentModeEl = document.getElementById("paymentMode");

// Toast Notification
function showToast(message, isError = false) {
    const toast = document.getElementById("toast");
    const toastMsg = document.getElementById("toastMsg");
    const toastIcon = document.getElementById("toastIcon");

    toastMsg.textContent = message;
    if (isError) {
        toastIcon.className = "fa-solid fa-circle-exclamation text-rose-400";
    } else {
        toastIcon.className = "fa-solid fa-circle-check text-emerald-400";
    }

    toast.classList.remove("translate-y-20", "opacity-0");
    setTimeout(() => {
        toast.classList.add("translate-y-20", "opacity-0");
    }, 3500);
}

// 1. Initialize Application
async function initApp() {
    await fetchShows();
    attachEventListeners();
}

async function fetchShows() {
    try {
        const res = await fetch("/api/shows");
        const data = await res.json();
        if (data.status === "success" && data.shows.length > 0) {
            appState.shows = data.shows;
            // Default select the first show if not already selected
            if (!appState.selectedShowId) {
                appState.selectedShowId = data.shows[0].show_id;
            }
            renderShows();
            renderTiers();
            triggerRecalculate();
        }
    } catch (err) {
        showToast("Error loading shows: " + err.message, true);
    }
}

// 2. Render Shows List
function renderShows() {
    showsListEl.innerHTML = "";
    appState.shows.forEach(show => {
        const isSelected = show.show_id === appState.selectedShowId;
        const card = document.createElement("div");
        card.className = `show-card p-3.5 rounded-xl border bg-slate-950/60 ${isSelected ? "active border-amber-500" : "border-slate-800"}`;
        
        // Count sold out tiers
        const tierEntries = Object.values(show.tiers);
        const soldOutTiers = tierEntries.filter(t => t.is_sold_out).length;
        
        card.innerHTML = `
            <div class="flex items-start justify-between gap-1 mb-1.5">
                <h4 class="font-bold text-sm text-slate-100 truncate">${show.movie_title}</h4>
                ${isSelected ? '<span class="text-[10px] bg-amber-500 text-slate-950 px-1.5 py-0.5 rounded font-black">SELECTED</span>' : ''}
            </div>
            <div class="text-[11px] text-slate-400 space-y-0.5">
                <div class="text-amber-400/90 font-medium">${show.screen_name}</div>
                <div class="flex items-center gap-1 text-slate-300">
                    <i class="fa-regular fa-clock text-[10px]"></i> ${show.show_time}
                </div>
            </div>
            <div class="mt-2.5 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px]">
                <span class="text-slate-500">${show.experience}</span>
                ${soldOutTiers > 0 ? `<span class="text-rose-400 font-semibold text-[10px]"><i class="fa-solid fa-triangle-exclamation"></i> ${soldOutTiers} Tier Sold Out</span>` : '<span class="text-emerald-400 text-[10px]">All Tiers Available</span>'}
            </div>
        `;

        card.addEventListener("click", () => {
            if (appState.selectedShowId !== show.show_id) {
                appState.selectedShowId = show.show_id;
                // Reset selected quantities when switching show
                appState.selectedQuantities = { Silver: 0, Gold: 0, Recliner: 0 };
                renderShows();
                renderTiers();
                triggerRecalculate();
            }
        });

        showsListEl.appendChild(card);
    });

    const activeShow = getActiveShow();
    if (activeShow) {
        billMovieTitleEl.textContent = activeShow.movie_title;
        billScreenTimeEl.textContent = `${activeShow.screen_name} • ${activeShow.show_time}`;
        activeShowBadgeEl.textContent = `${activeShow.screen_name}`;
    }
}

function getActiveShow() {
    return appState.shows.find(s => s.show_id === appState.selectedShowId);
}

// 3. Render Seating Tiers & Inventory Controls
function renderTiers() {
    tiersContainerEl.innerHTML = "";
    const activeShow = getActiveShow();
    if (!activeShow) return;

    ["Silver", "Gold", "Recliner"].forEach(tierName => {
        const tier = activeShow.tiers[tierName];
        if (!tier) return;

        const qty = appState.selectedQuantities[tierName] || 0;
        const isSoldOut = tier.is_sold_out;
        const maxAllowed = tier.available_seats;

        const card = document.createElement("div");
        card.className = `tier-card p-4 rounded-xl border bg-slate-950/60 flex flex-col justify-between ${isSoldOut ? "sold-out" : "border-slate-800"}`;

        let statusBadge = "";
        if (isSoldOut) {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30">SOLD OUT</span>`;
        } else if (tier.available_seats <= 5) {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30">${tier.available_seats} LEFT</span>`;
        } else {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">${tier.available_seats} AVAIL</span>`;
        }

        card.innerHTML = `
            <div>
                <div class="flex items-center justify-between gap-1 mb-1">
                    <h4 class="font-bold text-sm text-slate-100">${tier.tier}</h4>
                    ${statusBadge}
                </div>
                <div class="text-lg font-black text-amber-400 font-mono mb-2">
                    ${tier.base_price_formatted}
                    <span class="text-[10px] text-slate-400 font-normal">/seat</span>
                </div>
            </div>

            <!-- Seat Counter Controls -->
            <div class="pt-2 border-t border-slate-800/80">
                <div class="flex items-center justify-between bg-slate-900 rounded-lg p-1 border border-slate-800">
                    <button type="button" class="btn-minus w-8 h-8 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-200 flex items-center justify-center font-bold text-sm transition disabled:opacity-30 disabled:cursor-not-allowed"
                        ${qty <= 0 || isSoldOut ? "disabled" : ""}>
                        <i class="fa-solid fa-minus text-xs"></i>
                    </button>
                    
                    <span class="font-mono font-bold text-sm px-2 ${qty > 0 ? 'text-amber-400' : 'text-slate-500'}">
                        ${qty}
                    </span>

                    <button type="button" class="btn-plus w-8 h-8 rounded-md bg-amber-500 hover:bg-amber-400 text-slate-950 flex items-center justify-center font-bold text-sm transition disabled:opacity-30 disabled:cursor-not-allowed"
                        ${qty >= maxAllowed || isSoldOut ? "disabled" : ""}>
                        <i class="fa-solid fa-plus text-xs"></i>
                    </button>
                </div>
                ${isSoldOut ? '<p class="text-[10px] text-rose-400 mt-1 text-center font-medium">Tier Sold Out</p>' : ''}
            </div>
        `;

        // Event listeners for counter
        const btnMinus = card.querySelector(".btn-minus");
        const btnPlus = card.querySelector(".btn-plus");

        if (btnMinus) {
            btnMinus.addEventListener("click", () => {
                if (appState.selectedQuantities[tierName] > 0) {
                    appState.selectedQuantities[tierName]--;
                    renderTiers();
                    triggerRecalculate();
                }
            });
        }

        if (btnPlus) {
            btnPlus.addEventListener("click", () => {
                if (appState.selectedQuantities[tierName] < maxAllowed) {
                    appState.selectedQuantities[tierName]++;
                    renderTiers();
                    triggerRecalculate();
                } else {
                    showToast(`Only ${maxAllowed} seats available in ${tierName}!`, true);
                }
            });
        }

        tiersContainerEl.appendChild(card);
    });
    renderVisualSeatGrid();
}

function renderVisualSeatGrid() {
    const gridEl = document.getElementById("visualSeatGrid");
    if (!gridEl) return;
    gridEl.innerHTML = "";
    const activeShow = getActiveShow();
    if (!activeShow) return;

    const rowConfigs = [
        { row: "A", tier: "Recliner", count: 12 },
        { row: "B", tier: "Gold", count: 14 },
        { row: "C", tier: "Gold", count: 14 },
        { row: "D", tier: "Silver", count: 16 },
        { row: "E", tier: "Silver", count: 16 }
    ];

    rowConfigs.forEach(cfg => {
        const tierInfo = activeShow.tiers[cfg.tier] || { is_sold_out: false, available_seats: 0 };
        const rowDiv = document.createElement("div");
        rowDiv.className = "flex items-center gap-2";

        const labelSpan = document.createElement("span");
        labelSpan.className = "w-24 text-[10px] font-mono text-slate-400 font-bold shrink-0";
        labelSpan.textContent = `Row ${cfg.row} (${cfg.tier})`;
        rowDiv.appendChild(labelSpan);

        const seatsContainer = document.createElement("div");
        seatsContainer.className = "flex items-center gap-1.5 flex-wrap";

        for (let i = 1; i <= cfg.count; i++) {
            const seatId = `${cfg.row}${i}`;
            const isSelected = appState.selectedSeatIds.includes(seatId);
            const isOccupied = tierInfo.is_sold_out || (i > tierInfo.available_seats && !isSelected);

            const seatBtn = document.createElement("button");
            seatBtn.type = "button";
            seatBtn.dataset.seatId = seatId;
            seatBtn.dataset.tier = cfg.tier;

            const baseClass = "w-6 h-6 rounded text-[9px] font-mono font-bold flex items-center justify-center transition";
            if (isOccupied) {
                seatBtn.className = `${baseClass} bg-rose-950/40 border border-rose-900 text-rose-500 cursor-not-allowed opacity-50`;
                seatBtn.textContent = "✕";
                seatBtn.disabled = true;
                seatBtn.title = `${seatId} (${cfg.tier}) - Booked`;
            } else if (isSelected) {
                seatBtn.className = `${baseClass} bg-amber-500 text-slate-950 border border-amber-400 font-black shadow`;
                seatBtn.textContent = i;
                seatBtn.title = `${seatId} (${cfg.tier}) - Selected`;
            } else {
                seatBtn.className = `${baseClass} bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 hover:border-amber-500/60 cursor-pointer`;
                seatBtn.textContent = i;
                seatBtn.title = `${seatId} (${cfg.tier}) - Available`;
            }

            if (!isOccupied) {
                seatBtn.addEventListener("click", () => {
                    toggleSeatSelection(seatId, cfg.tier);
                });
            }

            seatsContainer.appendChild(seatBtn);
        }

        rowDiv.appendChild(seatsContainer);
        gridEl.appendChild(rowDiv);
    });
}

function toggleSeatSelection(seatId, tier) {
    const activeShow = getActiveShow();
    if (!activeShow) return;
    const tierInfo = activeShow.tiers[tier];
    if (!tierInfo) return;

    const idx = appState.selectedSeatIds.indexOf(seatId);
    if (idx > -1) {
        appState.selectedSeatIds.splice(idx, 1);
        appState.selectedQuantities[tier] = Math.max(0, (appState.selectedQuantities[tier] || 0) - 1);
    } else {
        if ((appState.selectedQuantities[tier] || 0) >= tierInfo.available_seats) {
            showToast(`No more seats available in ${tier}!`, true);
            return;
        }
        appState.selectedSeatIds.push(seatId);
        appState.selectedQuantities[tier] = (appState.selectedQuantities[tier] || 0) + 1;
    }

    renderTiers();
    triggerRecalculate();
}


// 4. Live Pricing Engine Recalculation
async function triggerRecalculate() {
    const activeShow = getActiveShow();
    if (!activeShow) return;

    const items = Object.entries(appState.selectedQuantities)
        .filter(([_, qty]) => qty > 0)
        .map(([tier, qty]) => ({ tier, quantity: qty }));

    const totalTickets = items.reduce((sum, item) => sum + item.quantity, 0);
    billTicketCountBadgeEl.textContent = `${totalTickets} Seat${totalTickets !== 1 ? 's' : ''}`;

    if (totalTickets === 0) {
        resetBillUI();
        btnBookEl.disabled = true;
        return;
    }

    const payload = {
        show_id: appState.selectedShowId,
        items: items,
        offers: {
            enable_festival_discount: appState.offers.enableFestival,
            festival_flat_discount: 50.00,
            enable_member_discount: appState.offers.enableMember,
            member_discount_percent: 15.00,
            member_discount_max_cap: 100.00,
            member_id: appState.offers.memberId
        }
    };

    try {
        const res = await fetch("/api/pricing/calculate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (data.status === "success") {
            appState.latestPricing = data.pricing;
            updateBillUI(data.pricing);
            btnBookEl.disabled = false;
        } else {
            showToast(data.message, true);
        }
    } catch (err) {
        console.error("Calculation failed:", err);
    }
}

// 5. Update Bill UI Elements
function updateBillUI(pricing) {
    // Line Items Container
    lineItemsContainerEl.innerHTML = "";
    pricing.line_items.forEach(item => {
        const row = document.createElement("div");
        row.className = "flex items-center justify-between py-1.5 px-2 rounded-lg bg-slate-950/40 hover:bg-slate-950 border border-slate-800/40 text-xs";

        let badgeClass = "bg-slate-800 text-slate-300";
        if (item.category === "DISCOUNT") badgeClass = "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
        if (item.category === "FEE") badgeClass = "bg-sky-500/10 text-sky-400 border border-sky-500/20";
        if (item.category === "TAX") badgeClass = "bg-purple-500/10 text-purple-400 border border-purple-500/20";

        row.innerHTML = `
            <div class="flex items-center gap-2 truncate mr-2">
                <span class="text-[9px] px-1.5 py-0.5 rounded font-mono uppercase font-bold ${badgeClass}">
                    ${item.category}
                </span>
                <span class="text-slate-300 truncate">${item.description}</span>
            </div>
            <div class="font-mono font-semibold whitespace-nowrap ${item.amount < 0 ? 'text-emerald-400' : 'text-slate-200'}">
                ${item.amount_fmt}
            </div>
        `;
        lineItemsContainerEl.appendChild(row);
    });

    // Summary Figures
    summaryGrossEl.textContent = pricing.gross_ticket_amount_fmt;
    
    if (pricing.total_discount_applied > 0) {
        summaryDiscountRowEl.style.display = "flex";
        summaryDiscountEl.textContent = `-${pricing.total_discount_applied_fmt}`;
    } else {
        summaryDiscountRowEl.style.display = "none";
    }

    summaryNetTicketsEl.textContent = pricing.net_ticket_amount_fmt;
    summaryFeeEl.textContent = pricing.total_convenience_fee_fmt;

    summaryTotalTaxEl.textContent = pricing.total_tax_fmt;
    summaryCgstTicketsEl.textContent = pricing.cgst_tickets_fmt;
    summarySgstTicketsEl.textContent = pricing.sgst_tickets_fmt;
    summaryCgstFeeEl.textContent = pricing.cgst_fee_fmt;
    summarySgstFeeEl.textContent = pricing.sgst_fee_fmt;

    summaryGrandTotalEl.textContent = pricing.grand_total_fmt;
    summaryGrandTotalEl.classList.add("flash-change");
    setTimeout(() => summaryGrandTotalEl.classList.remove("flash-change"), 400);

    // Sync UPI & Cash Due amounts
    const upiBadge = document.getElementById("upiAmountBadge");
    if (upiBadge) upiBadge.textContent = pricing.grand_total_fmt;

    const cashIn = document.getElementById("cashTenderedInput");
    const cashDue = document.getElementById("cashChangeDue");
    if (cashIn && cashDue) {
        const val = parseFloat(cashIn.value) || 0;
        const due = Math.max(0, val - pricing.grand_total);
        cashDue.textContent = `₹${due.toFixed(2)}`;
    }

    // Audit notes
    calculationAuditNotesEl.innerHTML = "";
    pricing.calculation_notes.forEach(note => {
        const noteEl = document.createElement("div");
        noteEl.innerHTML = `<i class="fa-solid fa-angle-right text-amber-500 text-[9px]"></i> ${note}`;
        calculationAuditNotesEl.appendChild(noteEl);
    });
}

function resetBillUI() {
    lineItemsContainerEl.innerHTML = `
        <div class="text-center py-8 text-slate-500 italic">
            Select seat quantities to view the live line-by-line itemized calculation.
        </div>
    `;
    summaryGrossEl.textContent = "₹0.00";
    summaryDiscountRowEl.style.display = "none";
    summaryNetTicketsEl.textContent = "₹0.00";
    summaryFeeEl.textContent = "₹0.00";
    summaryTotalTaxEl.textContent = "₹0.00";
    summaryCgstTicketsEl.textContent = "₹0.00";
    summarySgstTicketsEl.textContent = "₹0.00";
    summaryCgstFeeEl.textContent = "₹0.00";
    summarySgstFeeEl.textContent = "₹0.00";
    summaryGrandTotalEl.textContent = "₹0.00";
    calculationAuditNotesEl.innerHTML = "<div>No calculation notes yet.</div>";

    const upiBadge = document.getElementById("upiAmountBadge");
    if (upiBadge) upiBadge.textContent = "₹0.00";
}

// 6. Complete Booking & Generate Printable Thermal Receipt
async function handleBooking() {
    const activeShow = getActiveShow();
    if (!activeShow) return;

    const items = Object.entries(appState.selectedQuantities)
        .filter(([_, qty]) => qty > 0)
        .map(([tier, qty]) => ({ tier, quantity: qty }));

    if (items.length === 0) {
        showToast("Select at least 1 ticket to book!", true);
        return;
    }

    btnBookEl.disabled = true;
    btnBookEl.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Reserving Seats...`;

    const cashIn = document.getElementById("cashTenderedInput");
    const cashDue = document.getElementById("cashChangeDue");

    const payload = {
        show_id: appState.selectedShowId,
        items: items,
        offers: {
            enable_festival_discount: appState.offers.enableFestival,
            festival_flat_discount: 50.00,
            enable_member_discount: appState.offers.enableMember,
            member_discount_percent: 15.00,
            member_discount_max_cap: 100.00,
            member_id: appState.offers.memberId
        },
        customer_name: customerNameEl.value.trim() || "Counter Walk-in",
        customer_phone: customerPhoneEl.value.trim() || "N/A",
        payment_mode: paymentModeEl.value,
        selected_seats: appState.selectedSeatIds,
        cash_tendered: cashIn ? cashIn.value : null,
        change_due: cashDue ? cashDue.textContent : null
    };


    try {
        const res = await fetch("/api/bookings/create", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (data.status === "success") {
            showToast("Booking created successfully!");
            // Update catalog with decremented seats
            if (data.updated_shows) {
                appState.shows = data.updated_shows;
            }
            // Render thermal receipt modal
            renderThermalReceipt(data.receipt);
            receiptModal.classList.remove("hidden");

            // Reset selection for next customer in queue
            appState.selectedQuantities = { Silver: 0, Gold: 0, Recliner: 0 };
            appState.selectedSeatIds = [];
            renderShows();
            renderTiers();
            triggerRecalculate();
        } else {
            showToast(data.message, true);
        }
    } catch (err) {
        showToast("Booking failed: " + err.message, true);
    } finally {
        btnBookEl.disabled = false;
        btnBookEl.innerHTML = `<i class="fa-solid fa-print"></i> <span>Confirm Booking & Issue Receipt</span>`;
    }
}

function renderThermalReceipt(receipt) {
    const p = receipt.pricing;
    const ticketRows = p.line_items.filter(item => item.category === "TICKET").map(item => `
        <div class="flex justify-between py-0.5">
            <span>${item.description} x${item.quantity}</span>
            <span>${item.amount_fmt}</span>
        </div>
    `).join("");

    thermalReceiptContent.innerHTML = `
        <div class="text-center pb-2 border-b border-dashed border-slate-400">
            <div class="font-black text-sm uppercase">CinePay Multiplex</div>
            <div class="text-[10px] text-slate-600">Galaxy Mall • Screen POS Counter #04</div>
            <div class="text-[10px] font-bold mt-1">TAX INVOICE / CINEMA PASS</div>
            <div class="text-[9px] text-slate-500">GSTIN: 07AAAAA0000A1Z5</div>
        </div>

        <div class="text-[11px] py-2 border-b border-dashed border-slate-300 space-y-0.5">
            <div class="flex justify-between"><span>Booking ID:</span> <strong class="font-bold">${receipt.booking_id}</strong></div>
            <div class="flex justify-between"><span>Date/Time:</span> <span>${receipt.timestamp}</span></div>
            <div class="flex justify-between"><span>Customer:</span> <span>${receipt.customer_name}</span></div>
            <div class="flex justify-between"><span>Payment:</span> <span>${receipt.payment_mode}</span></div>
        </div>

        <div class="text-[11px] py-2 border-b border-dashed border-slate-300">
            <div class="font-bold uppercase text-xs">${receipt.movie_title}</div>
            <div class="text-slate-600">${receipt.screen_name}</div>
            <div class="font-semibold text-sky-800">${receipt.show_time}</div>
            ${receipt.selected_seats && receipt.selected_seats.length > 0 ? `
            <div class="mt-1 text-slate-800 font-bold bg-amber-500/20 px-2 py-0.5 rounded border border-amber-500/30">
                Seats: ${receipt.selected_seats.join(", ")}
            </div>
            ` : ''}
        </div>

        <div class="py-2 border-b border-dashed border-slate-300 text-[11px]">
            <div class="font-bold mb-1">TICKETS:</div>
            ${ticketRows}
            <div class="flex justify-between font-semibold pt-1 border-t border-slate-200">
                <span>Gross Tickets:</span>
                <span>${p.gross_ticket_amount_fmt}</span>
            </div>
            ${p.total_discount_applied > 0 ? `
            <div class="flex justify-between text-emerald-700 font-bold">
                <span>Total Discounts:</span>
                <span>-${p.total_discount_applied_fmt}</span>
            </div>
            <div class="flex justify-between font-bold">
                <span>Net Tickets:</span>
                <span>${p.net_ticket_amount_fmt}</span>
            </div>
            ` : ''}
            <div class="flex justify-between pt-1">
                <span>Convenience Fee:</span>
                <span>${p.total_convenience_fee_fmt}</span>
            </div>
        </div>

        <div class="py-1 text-[10px] text-slate-600 border-b border-dashed border-slate-300 space-y-0.5">
            <div class="flex justify-between"><span>CGST on Tickets (9%):</span> <span>${p.cgst_tickets_fmt}</span></div>
            <div class="flex justify-between"><span>SGST on Tickets (9%):</span> <span>${p.sgst_tickets_fmt}</span></div>
            <div class="flex justify-between"><span>CGST on Fee (9%):</span> <span>${p.cgst_fee_fmt}</span></div>
            <div class="flex justify-between"><span>SGST on Fee (9%):</span> <span>${p.sgst_fee_fmt}</span></div>
            <div class="flex justify-between font-bold text-slate-900 pt-0.5">
                <span>Total GST (18%):</span>
                <span>${p.total_tax_fmt}</span>
            </div>
        </div>

        ${receipt.payment_mode === "Cash" && receipt.cash_tendered ? `
        <div class="py-1 text-[10px] text-slate-700 border-b border-dashed border-slate-300 space-y-0.5">
            <div class="flex justify-between"><span>Cash Tendered:</span> <span class="font-mono">₹${parseFloat(receipt.cash_tendered).toFixed(2)}</span></div>
            <div class="flex justify-between font-bold text-emerald-800"><span>Change Returned:</span> <span class="font-mono">${receipt.change_due || '₹0.00'}</span></div>
        </div>
        ` : ''}

        <div class="py-2.5 my-1 border-t-2 border-b-2 border-slate-900 flex justify-between items-center text-sm font-black">
            <span>TOTAL PAID:</span>
            <span class="text-base">${p.grand_total_fmt}</span>
        </div>


        <div class="text-center text-[9px] text-slate-500 pt-1 leading-relaxed">
            <p>* Settled to the exact paisa *</p>
            <p>Thank you for choosing CinePay!</p>
            <div class="mt-2 text-[8px] tracking-widest text-slate-400 font-mono">
                ||||| | |||| ||| |||| | ||||| ||||
            </div>
        </div>
    `;
}

// 7. Event Listeners Setup
function attachEventListeners() {
    // Offers Toggles
    toggleFestivalEl.addEventListener("change", (e) => {
        appState.offers.enableFestival = e.target.checked;
        triggerRecalculate();
    });

    toggleMemberEl.addEventListener("change", (e) => {
        appState.offers.enableMember = e.target.checked;
        if (e.target.checked) {
            memberIdGroupEl.classList.remove("hidden");
        } else {
            memberIdGroupEl.classList.add("hidden");
        }
        triggerRecalculate();
    });

    memberIdInputEl.addEventListener("input", (e) => {
        appState.offers.memberId = e.target.value.trim();
        triggerRecalculate();
    });

    btnQuickMember.addEventListener("click", () => {
        memberIdInputEl.value = "VIP-9988";
        appState.offers.memberId = "VIP-9988";
        triggerRecalculate();
    });

    // Clear Button
    btnClearEl.addEventListener("click", () => {
        appState.selectedQuantities = { Silver: 0, Gold: 0, Recliner: 0 };
        appState.selectedSeatIds = [];
        toggleFestivalEl.checked = false;
        appState.offers.enableFestival = false;
        toggleMemberEl.checked = false;
        appState.offers.enableMember = false;
        memberIdGroupEl.classList.add("hidden");
        const cashIn = document.getElementById("cashTenderedInput");
        const cashDue = document.getElementById("cashChangeDue");
        if (cashIn) cashIn.value = "";
        if (cashDue) cashDue.textContent = "₹0.00";
        renderTiers();
        triggerRecalculate();
        showToast("Counter cleared for next customer.");
    });

    // Reset Demo Inventory
    btnResetEl.addEventListener("click", async () => {
        try {
            await fetch("/api/inventory/reset", { method: "POST" });
            appState.selectedQuantities = { Silver: 0, Gold: 0, Recliner: 0 };
            await fetchShows();
            showToast("Demo inventory refreshed.");
        } catch (err) {
            showToast("Reset failed: " + err.message, true);
        }
    });

    // Book Button
    btnBookEl.addEventListener("click", handleBooking);

    // Modal Close buttons
    btnCloseModal.addEventListener("click", () => receiptModal.classList.add("hidden"));
    btnDismissReceipt.addEventListener("click", () => receiptModal.classList.add("hidden"));
    btnPrintReceipt.addEventListener("click", () => window.print());

    // History Modal
    btnHistoryEl.addEventListener("click", async () => {
        historyModal.classList.remove("hidden");
        try {
            const res = await fetch("/api/bookings");
            const data = await res.json();
            if (data.status === "success") {
                if (data.bookings.length === 0) {
                    historyContainer.innerHTML = `<div class="text-center py-8 text-slate-500 text-xs">No bookings recorded yet in this session.</div>`;
                } else {
                    historyContainer.innerHTML = "";
                    data.bookings.forEach(b => {
                        const item = document.createElement("div");
                        item.className = "p-3.5 rounded-xl border border-slate-800 bg-slate-950/60 mb-2.5 flex justify-between items-center text-xs";
                        item.innerHTML = `
                            <div>
                                <div class="font-bold text-amber-400">${b.booking_id} • ${b.movie_title}</div>
                                <div class="text-slate-400 text-[11px]">${b.screen_name} • ${b.show_time}</div>
                                <div class="text-slate-500 text-[10px] mt-0.5">Cust: ${b.customer_name} | Paid: ${b.pricing.grand_total_fmt} via ${b.payment_mode}</div>
                            </div>
                            <div class="flex items-center gap-2">
                                <a href="/receipt/${b.booking_id}" target="_blank" class="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded border border-slate-700 text-xs">
                                    <i class="fa-solid fa-arrow-up-right-from-square"></i> Open Receipt
                                </a>
                            </div>
                        `;
                        historyContainer.appendChild(item);
                    });
                }
            }
        } catch (err) {
            historyContainer.innerHTML = `<div class="text-rose-400 text-xs">Failed to load history.</div>`;
        }
    });

    btnCloseHistoryModal.addEventListener("click", () => historyModal.classList.add("hidden"));

    // Rules Modal
    btnRulesEl.addEventListener("click", () => rulesModal.classList.remove("hidden"));
    btnCloseRulesModal.addEventListener("click", () => rulesModal.classList.add("hidden"));

    // THE TWIST: Messy Price List Importer Modal
    const btnImportPrices = document.getElementById("btnImportPrices");
    const importModal = document.getElementById("importModal");
    const btnCloseImportModal = document.getElementById("btnCloseImportModal");
    const btnLoadSampleCsv = document.getElementById("btnLoadSampleCsv");
    const btnRunSanitizer = document.getElementById("btnRunSanitizer");
    const rawPriceInput = document.getElementById("rawPriceInput");
    const applyCleanedToShow = document.getElementById("applyCleanedToShow");
    const importReportContainer = document.getElementById("importReportContainer");

    const statProcessed = document.getElementById("statProcessed");
    const statImported = document.getElementById("statImported");
    const statDeduplicated = document.getElementById("statDeduplicated");
    const statRejected = document.getElementById("statRejected");

    const importedRowsList = document.getElementById("importedRowsList");
    const deduplicatedList = document.getElementById("deduplicatedList");
    const rejectedList = document.getElementById("rejectedList");

    btnImportPrices.addEventListener("click", () => {
        importModal.classList.remove("hidden");
    });

    btnCloseImportModal.addEventListener("click", () => {
        importModal.classList.add("hidden");
    });

    btnLoadSampleCsv.addEventListener("click", async () => {
        try {
            const res = await fetch("/api/prices/sample");
            const data = await res.json();
            if (data.status === "success") {
                rawPriceInput.value = data.csv_content;
                showToast("Sample messy price list loaded!");
            }
        } catch (e) {
            showToast("Failed to load sample: " + e.message, true);
        }
    });

    btnRunSanitizer.addEventListener("click", async () => {
        const text = rawPriceInput.value.trim();
        if (!text) {
            showToast("Please enter or paste price list data first!", true);
            return;
        }

        btnRunSanitizer.disabled = true;
        btnRunSanitizer.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Sanitizing...`;

        try {
            const res = await fetch("/api/prices/import", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    csv_text: text,
                    apply_to_shows: applyCleanedToShow.checked,
                    show_id: appState.selectedShowId
                })
            });

            const data = await res.json();
            if (data.status === "success") {
                const report = data.report;
                
                // Update stats
                statProcessed.textContent = report.total_processed;
                statImported.textContent = report.imported_count;
                statDeduplicated.textContent = report.deduplicated_count;
                statRejected.textContent = report.rejected_count;

                // Render Cleaned & Imported Tiers
                importedRowsList.innerHTML = "";
                if (report.imported.length === 0) {
                    importedRowsList.innerHTML = `<tr><td colspan="4" class="p-3 text-center text-slate-500 italic">No valid tiers could be imported.</td></tr>`;
                } else {
                    report.imported.forEach(item => {
                        const tr = document.createElement("tr");
                        tr.className = "hover:bg-slate-900/80";
                        tr.innerHTML = `
                            <td class="p-2 font-bold text-emerald-400">${item.tier}</td>
                            <td class="p-2 font-black text-white">${item.price_formatted}</td>
                            <td class="p-2 text-slate-500">${item.original_tier || '-'}</td>
                            <td class="p-2 text-slate-500">${item.original_price || '-'}</td>
                        `;
                        importedRowsList.appendChild(tr);
                    });
                }

                // Render Deduplications
                deduplicatedList.innerHTML = "";
                if (report.deduplicated.length === 0) {
                    deduplicatedList.innerHTML = `<div class="p-2 text-slate-500 italic">No duplicate tier names detected.</div>`;
                } else {
                    report.deduplicated.forEach(d => {
                        const div = document.createElement("div");
                        div.className = "p-2 rounded bg-amber-950/20 border border-amber-800/40 text-amber-300 flex justify-between items-center";
                        div.innerHTML = `
                            <span><strong>${d.tier}</strong>: ${d.resolution}</span>
                            <span class="text-[10px] bg-amber-500/20 text-amber-400 px-1.5 py-0.5 rounded">Merged</span>
                        `;
                        deduplicatedList.appendChild(div);
                    });
                }

                // Render Rejections
                rejectedList.innerHTML = "";
                if (report.rejected.length === 0) {
                    rejectedList.innerHTML = `<div class="p-2 text-slate-500 italic">No records rejected. Perfect dataset!</div>`;
                } else {
                    report.rejected.forEach(r => {
                        const div = document.createElement("div");
                        div.className = "p-2 rounded bg-rose-950/20 border border-rose-800/40 text-rose-300 flex justify-between items-center";
                        div.innerHTML = `
                            <span>Row ${r.row_number || '?'}: <strong>'${r.raw_tier || '(blank)'}'</strong> @ '${r.raw_price || '(blank)'}'</span>
                            <span class="text-[10px] text-rose-400 font-semibold">${r.reason}</span>
                        `;
                        rejectedList.appendChild(div);
                    });
                }

                importReportContainer.classList.remove("hidden");
                showToast(`Price List Sanitized: ${report.imported_count} imported, ${report.deduplicated_count} deduplicated, ${report.rejected_count} rejected.`);

                // If updated shows were returned, refresh counter
                if (data.updated_shows) {
                    appState.shows = data.updated_shows;
                    renderShows();
                    renderTiers();
                    triggerRecalculate();
                }

            } else {
                showToast(data.message, true);
            }
        } catch (err) {
            showToast("Sanitizing failed: " + err.message, true);
        } finally {
            btnRunSanitizer.disabled = false;
            btnRunSanitizer.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i> Clean, De-duplicate & Audit`;
        }
    });

    // Tabs: Quick Counters vs Audi Seat Grid
    const btnTabCounters = document.getElementById("btnTabCounters");
    const btnTabSeatMap = document.getElementById("btnTabSeatMap");
    const seatMapContainer = document.getElementById("seatMapContainer");

    if (btnTabCounters && btnTabSeatMap && seatMapContainer) {
        btnTabCounters.addEventListener("click", () => {
            btnTabCounters.className = "px-2.5 py-1 rounded bg-amber-500 text-slate-950 font-bold flex items-center gap-1 transition";
            btnTabSeatMap.className = "px-2.5 py-1 rounded text-slate-400 hover:text-white font-medium flex items-center gap-1 transition";
            tiersContainerEl.classList.remove("hidden");
            seatMapContainer.classList.add("hidden");
        });

        btnTabSeatMap.addEventListener("click", () => {
            btnTabSeatMap.className = "px-2.5 py-1 rounded bg-amber-500 text-slate-950 font-bold flex items-center gap-1 transition";
            btnTabCounters.className = "px-2.5 py-1 rounded text-slate-400 hover:text-white font-medium flex items-center gap-1 transition";
            tiersContainerEl.classList.add("hidden");
            seatMapContainer.classList.remove("hidden");
            renderVisualSeatGrid();
        });
    }

    // Payment Mode toggle (Cash change calculator vs UPI QR preview)
    const cashChangeBox = document.getElementById("cashChangeBox");
    const upiQrBox = document.getElementById("upiQrBox");
    const cashTenderedInput = document.getElementById("cashTenderedInput");
    const cashChangeDue = document.getElementById("cashChangeDue");

    if (paymentModeEl) {
        paymentModeEl.addEventListener("change", (e) => {
            const mode = e.target.value;
            if (mode === "Cash") {
                if (cashChangeBox) cashChangeBox.classList.remove("hidden");
                if (upiQrBox) upiQrBox.classList.add("hidden");
            } else if (mode === "UPI") {
                if (cashChangeBox) cashChangeBox.classList.add("hidden");
                if (upiQrBox) upiQrBox.classList.remove("hidden");
            } else {
                if (cashChangeBox) cashChangeBox.classList.add("hidden");
                if (upiQrBox) upiQrBox.classList.add("hidden");
            }
        });
    }

    if (cashTenderedInput && cashChangeDue) {
        cashTenderedInput.addEventListener("input", () => {
            const tendered = parseFloat(cashTenderedInput.value) || 0;
            const grandTotal = appState.latestPricing ? appState.latestPricing.grand_total : 0;
            const change = Math.max(0, tendered - grandTotal);
            cashChangeDue.textContent = `₹${change.toFixed(2)}`;
        });
    }

    // Manager Analytics Dashboard
    const btnAnalytics = document.getElementById("btnAnalytics");
    const analyticsModal = document.getElementById("analyticsModal");
    const btnCloseAnalyticsModal = document.getElementById("btnCloseAnalyticsModal");

    if (btnAnalytics && analyticsModal) {
        btnAnalytics.addEventListener("click", async () => {
            analyticsModal.classList.remove("hidden");
            try {
                const res = await fetch("/api/analytics");
                const data = await res.json();
                if (data.status === "success") {
                    const a = data.analytics;
                    document.getElementById("analyticsRev").textContent = a.total_revenue_fmt;
                    document.getElementById("analyticsTax").textContent = a.total_tax_collected_fmt;
                    document.getElementById("analyticsFees").textContent = a.total_fees_collected_fmt;
                    document.getElementById("analyticsDisc").textContent = a.total_discounts_given_fmt;
                    document.getElementById("analyticsTxCount").textContent = a.total_transactions;
                    document.getElementById("analyticsTixCount").textContent = a.total_tickets_sold;
                    document.getElementById("analyticsOccupancy").textContent = a.occupancy_pct + "%";
                    document.getElementById("analyticsSilverTix").textContent = a.tier_counts ? (a.tier_counts.Silver || 0) : 0;
                    document.getElementById("analyticsGoldTix").textContent = a.tier_counts ? (a.tier_counts.Gold || 0) : 0;
                    document.getElementById("analyticsReclinerTix").textContent = a.tier_counts ? (a.tier_counts.Recliner || 0) : 0;
                }
            } catch (err) {
                showToast("Failed to load analytics: " + err.message, true);
            }
        });
    }

    if (btnCloseAnalyticsModal && analyticsModal) {
        btnCloseAnalyticsModal.addEventListener("click", () => {
            analyticsModal.classList.add("hidden");
        });
    }

    // Keyboard Shortcuts (Fast counter cashier operations)
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            receiptModal.classList.add("hidden");
            historyModal.classList.add("hidden");
            rulesModal.classList.add("hidden");
            importModal.classList.add("hidden");
            if (analyticsModal) analyticsModal.classList.add("hidden");
        }
    });
}


// Start application on DOM ready
document.addEventListener("DOMContentLoaded", initApp);
