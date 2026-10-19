let connectionForms = [];

function drawConnectionFields() {
  for (const button of $('database-cards').children) {
    button.setAttribute('aria-pressed', String(button.dataset.type === $('database-type').value));
  }
  const form = connectionForms.find((item) => item.type === $('database-type').value);
  $('connection-fields').replaceChildren();
  for (const field of form.fields) {
    const label = document.createElement('label');
    label.textContent = field.label;
    const input = document.createElement('input');
    input.name = field.name;
    input.type = field.type;
    input.value = field.default;
    input.maxLength = 4096;
    input.autocomplete = 'off';
    input.dir = 'ltr';
    input.required = field.name === 'database';
    label.append(input);
    $('connection-fields').append(label);
  }
}

async function loadConnectionForms() {
  if (connectionForms.length) return;
  connectionForms = await (await request('/setup/databases')).json();
  for (const form of connectionForms) {
    const option = document.createElement('option');
    option.value = form.type;
    option.textContent = form.type === 'mongodb' ? 'MongoDB' : form.type === 'mysql' ? 'MySQL / MariaDB' : form.type;
    $('database-type').append(option);
    const card = document.createElement('button');
    card.type = 'button';
    card.textContent = option.textContent;
    card.dataset.type = form.type;
    card.addEventListener('click', () => {
      $('database-type').value = form.type;
      drawConnectionFields();
    });
    $('database-cards').append(card);
  }
  drawConnectionFields();
  const status = await (await request('/status')).json();
  $('setup').hidden = status.configured;
}

async function testConnection(event) {
  event.preventDefault();
  $('connection-test').disabled = true;
  $('connection-result').textContent = 'در حال آزمایش اتصال…';
  const values = Object.fromEntries(new FormData($('connection-form')));
  try {
    const response = await request('/setup/test', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ db_type: $('database-type').value, values, advanced_uri: $('connection-uri').value }) });
    const result = await response.json();
    $('connection-result').textContent = result.message;
    if (result.ok) {
      $('connection-uri').value = '';
      $('connection-fields').querySelector('[name="password"]').value = '';
      await loadSources();
    } else {
      $('source-step').hidden = true;
      $('readonly-help').hidden = true;
    }
  } catch (error) {
    $('connection-result').textContent = error instanceof TypeError ? 'ارتباط با برنامه قطع شد؛ دوباره رصام را باز کنید.' : error.message;
  } finally { $('connection-test').disabled = false; }
}

$('setup-open').addEventListener('click', () => { $('setup').hidden = !$('setup').hidden; });
$('database-type').addEventListener('change', drawConnectionFields);
$('connection-form').addEventListener('submit', testConnection);
