// قیمت و مدل از D1 می‌آیند؛ تغییر پلن، قرارداد لایسنس صادرشده را عوض نمی‌کند.
let products = [];

function field(form, key, label, type = 'text', value = '') {
  const wrap = document.createElement('label');
  wrap.textContent = label;
  const input = document.createElement(key === 'description' ? 'textarea' : 'input');
  input.name = key;
  if (input.tagName === 'INPUT') input.type = type;
  input.value = value ?? '';
  if (type === 'number') { input.min = key === 'daily_limit' ? '1' : '0'; input.step = '1'; }
  input.maxLength = key === 'description' ? 300 : key === 'title' ? 80 : 200;
  if (key === 'model') { input.dir = 'ltr'; input.placeholder = 'provider/model'; }
  if (type === 'checkbox') { input.checked = !!value; input.value = 'on'; wrap.className = 'product-published'; }
  wrap.append(input);
  form.append(wrap);
  return input;
}

function choices() {
  const select = document.getElementById('product-choice');
  const previous = select.value;
  select.replaceChildren(new Option('بدون پلن فروش · تنظیم دستی', ''));
  for (const product of products.filter((p) => p.published && p.model)) {
    select.append(new Option(product.title, product.id));
  }
  select.value = previous;
  updateIssueFields();
}

function updateIssueFields() {
  const selected = products.find((p) => p.id === document.getElementById('product-choice').value);
  const quota = document.getElementById('daily-limit');
  quota.readOnly = !!selected;
  if (selected) quota.value = selected.daily_limit;
  document.getElementById('product-model').textContent = selected ? `مدل: ${selected.model}` : 'مدل پیش‌فرض سرور استفاده می‌شود.';
}

function values(form) {
  const data = new FormData(form);
  const price = (key) => data.get(key).trim() === '' ? null : Number(data.get(key));
  return { title: data.get('title'), description: data.get('description'), model: data.get('model'),
    daily_limit: Number(data.get('daily_limit')), monthly_price: price('monthly_price'),
    yearly_price: price('yearly_price'), published: data.get('published') === 'on' };
}

function editor(product, api) {
  const form = document.createElement('form');
  form.className = 'product-editor';
  const heading = document.createElement('h3');
  heading.textContent = product.title;
  form.append(heading);
  field(form, 'title', 'نام پلن', 'text', product.title);
  field(form, 'description', 'توضیح کوتاه', 'text', product.description);
  field(form, 'model', 'شناسهٔ مدل سرویس فعلی', 'text', product.model);
  field(form, 'daily_limit', 'ظرفیت فراخوانی مدل در روز (UTC)', 'number', product.daily_limit);
  field(form, 'monthly_price', 'قیمت ماهانه · تومان (خالی = عرضه نشود)', 'number', product.monthly_price);
  field(form, 'yearly_price', 'قیمت سالانه · تومان (خالی = عرضه نشود)', 'number', product.yearly_price);
  field(form, 'published', 'نمایش در سایت', 'checkbox', product.published);
  const button = document.createElement('button');
  button.textContent = 'ذخیرهٔ پلن';
  const status = document.createElement('p');
  status.setAttribute('role', 'status');
  form.append(button, status);
  form.addEventListener('submit', async (event) => {
    event.preventDefault(); button.disabled = true;
    try {
      const result = await api(`/api/products/${product.id}`, values(form));
      products = products.map((p) => p.id === product.id ? result.product : p);
      heading.textContent = result.product.title;
      choices();
      status.textContent = 'ذخیره شد؛ لایسنس‌های قبلی تغییری نمی‌کنند.';
    } catch (error) { status.textContent = error.message; }
    finally { button.disabled = false; }
  });
  return form;
}

export async function setupProducts(api) {
  const target = document.getElementById('product-editors');
  try {
    products = (await api('/api/products')).products;
    target.replaceChildren(...products.map((product) => editor(product, api)));
    choices();
    document.getElementById('product-choice').addEventListener('change', updateIssueFields);
  } catch (error) { target.textContent = error.message; }
}

export function productTitle(id) {
  return products.find((product) => product.id === id)?.title || id;
}
