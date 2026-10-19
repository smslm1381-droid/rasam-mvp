// هیچ مبلغی از مرورگر به درگاه ارسال نمی‌شود؛ اتصال پرداخت هنوز ساخته نشده است.
let purchasePlans = [];
let billingPeriod = 'monthly';
const purchaseNumber = new Intl.NumberFormat('fa-IR');

function paragraph(text, className = '') {
  const p = document.createElement('p');
  p.textContent = text;
  p.className = className;
  return p;
}

function checkout(plan) {
  const period = billingPeriod === 'monthly' ? 'ماهانه · ۳۰ روز' : 'سالانه · ۳۶۵ روز';
  const price = plan[billingPeriod + '_price'];
  if (price == null) return;
  document.getElementById('checkout-summary').replaceChildren(
    paragraph(plan.title), paragraph(period), paragraph(purchaseNumber.format(price) + ' تومان', 'plan-price'),
    paragraph(plan.model, 'plan-model'), paragraph(`${purchaseNumber.format(plan.daily_limit)} فراخوانی مدل در روز`));
  document.getElementById('checkout-dialog').showModal();
}

function drawPlans() {
  const cards = purchasePlans.map((plan) => {
    const card = document.createElement('article');
    card.className = 'purchase-plan';
    const title = document.createElement('h3');
    title.textContent = plan.title;
    const price = plan[billingPeriod + '_price'];
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = price == null ? 'این دوره عرضه نمی‌شود' : 'انتخاب پلن';
    button.disabled = price == null;
    button.addEventListener('click', () => checkout(plan));
    card.append(title, paragraph(plan.description, 'muted'),
      paragraph(price == null ? '—' : purchaseNumber.format(price) + ' تومان', 'plan-price'),
      paragraph(plan.model, 'plan-model'), paragraph(`${purchaseNumber.format(plan.daily_limit)} فراخوانی مدل در روز`), button);
    return card;
  });
  document.getElementById('purchase-plans').replaceChildren(...cards);
}

async function loadPlans() {
  const status = document.getElementById('purchase-status');
  try {
    const response = await fetch('/plans.json', { cache: 'no-store' });
    if (!response.ok) throw new Error('unavailable');
    const data = await response.json();
    if (!Array.isArray(data.plans)) throw new Error('invalid');
    purchasePlans = data.plans;
    drawPlans();
    status.textContent = purchasePlans.length ? '' : 'جزئیات پلن‌ها به‌زودی اعلام می‌شود.';
  } catch { status.textContent = 'اطلاعات پلن‌ها اکنون در دسترس نیست؛ کمی بعد دوباره تلاش کنید.'; }
}
for (const button of document.querySelectorAll('[data-period]')) {
  button.addEventListener('click', () => {
    billingPeriod = button.dataset.period;
    for (const item of document.querySelectorAll('[data-period]')) item.setAttribute('aria-pressed', String(item === button));
    drawPlans();
  });
}
document.getElementById('checkout-close').addEventListener('click', () => document.getElementById('checkout-dialog').close());
loadPlans();
