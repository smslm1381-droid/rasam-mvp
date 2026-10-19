let teachingInputs = [];
let teachingCustomer = null;

function teachingRow(field) {
  const row = document.createElement('tr');
  const title = document.createElement('td');
  title.textContent = `${field.name} (${field.sources.join('، ')})`;
  const inputs = {};
  row.append(title);
  for (const key of ['label', 'note']) {
    const cell = document.createElement('td');
    const input = document.createElement(key === 'note' ? 'textarea' : 'input');
    input.value = field[key];
    input.maxLength = key === 'label' ? 120 : 2000;
    input.setAttribute('aria-label', `${key === 'label' ? 'نام فارسی' : 'توضیح'} ${field.name}`);
    cell.append(input);
    row.append(cell);
    inputs[key] = input;
  }
  teachingInputs.push({ name: field.name, ...inputs });
  $('teaching-fields').append(row);
}

async function openTeaching() {
  $('teaching').hidden = false;
  $('teaching-notice').textContent = 'در حال خواندن ستون‌ها…';
  try {
    const result = await (await request('/knowledge')).json();
    if (!result.ok) { $('teaching-notice').textContent = result.message; return; }
    teachingInputs = [];
    teachingCustomer = result.customer;
    $('field-search').value = '';
    $('teaching-fields').replaceChildren();
    for (const field of result.fields) teachingRow(field);
    $('documentation').value = result.documentation;
    $('required-documentation-text').textContent = result.required_documentation || '';
    $('required-documentation').hidden = !result.required_documentation;
    $('teaching-notice').textContent = '';
  } catch (error) { $('teaching-notice').textContent = error.message; }
}

async function saveTeaching(event) {
  event.preventDefault();
  $('teaching-save').disabled = true;
  try {
    const fields = teachingInputs.map((item) => ({ name: item.name, label: item.label.value, note: item.note.value }));
    const result = await (await request('/knowledge', { method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ customer: teachingCustomer, fields, documentation: $('documentation').value }) })).json();
    if (result.ok) await openTeaching();
    $('teaching-notice').textContent = result.message;
  } catch (error) { $('teaching-notice').textContent = error.message; }
  finally { $('teaching-save').disabled = false; }
}

async function sendFeedback(rating) {
  const button = $(`feedback-${rating}`);
  button.disabled = true;
  try {
    const result = await (await request(`/feedback/${answerId}/${rating}`, { method: 'POST' })).json();
    $('feedback-notice').textContent = result.message;
    button.disabled = result.ok;
  } catch (error) { $('feedback-notice').textContent = error.message; button.disabled = false; }
}

$('teaching-open').addEventListener('click', openTeaching);
$('teaching-form').addEventListener('submit', saveTeaching);
$('field-search').addEventListener('input', () => {
  const query = $('field-search').value.toLocaleLowerCase();
  for (const row of $('teaching-fields').children) row.hidden = !row.firstChild.textContent.toLocaleLowerCase().includes(query);
});
$('feedback-positive').addEventListener('click', () => sendFeedback('positive'));
$('feedback-negative').addEventListener('click', () => sendFeedback('negative'));
