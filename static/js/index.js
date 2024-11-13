import $ from 'jquery';
import { defaultOptions } from '/libs/options.js';

const pageState = {
    title: document.title,
    url: location.href,
    baseurl: location.href.split('#')[0],
};

function buildCGI() {
  const params = {};
  const items = $('#id_main_form').serializeArray();
  items.forEach((item) => {
    if (item.value === "") {
      return;
    }
    if (/advanced|csrf_token|manifest|mode|model|mpd|stream/.test(item.name)) {
      return;
    }
    const dflt = defaultOptions[item.name];
    if (item.value !== `${dflt}`) {
      if (params[item.name] !== undefined) {
        if (typeof params[item.name] !== 'object') {
          params[item.name] = [params[item.name], item.value,];
        } else {
          params[item.name].push(item.value);
        }
      } else {
        params[item.name] = item.value;
      }
    }
  });
  const drms = [];
  ['clearkey', 'marlin', 'playready',].forEach(name => {
    if (params[`${name}__enabled`] === 'on') {
      const drmloc = `${name}_drmloc`;
      if (params[drmloc] === undefined || params[drmloc] === "") {
        drms.push(name);
      } else {
        drms.push(`${name}-${params[drmloc]}`);
      }
      delete params[drmloc];
      delete params[`drm_${name}`];
    }
  });
  if (drms.length) {
    params.drm = `${drms.join(',')}`;
  }
  const rv = {};
  for (const [key, value] of Object.entries(params)) {
    rv[key] = `${key}=${value}`;
  }
  return rv;
}

function getSelectedMode() {
  const options = $('input[name="mode"]');
  for(let i=0; i < options.length; ++i) {
    if (options[i].checked) {
      return {
        value: options[i].value,
        title: options[i].labels[0].innerText,
      };
    }
  }
  return null;
}

function getSelectedStream() {
  const options = $('input[name="stream"]');
  for(let i=0; i < options.length; ++i) {
    if (options[i].checked) {
      return {
        value: options[i].value,
        title: options[i].labels[0].innerText,
      };
    }
  }
  return null;
}

function calculateManifestURL() {
  const stream = getSelectedStream();
  if (!stream) {
    return '';
  }
  const manifest = $('#model-manifest').val();
  const mode = getSelectedMode();
  const isMpsStream = /^mps\./.test(stream.value);
  const template = $('#with-modules').data(
    isMpsStream ? 'mps-url-template': 'stream-url-template');
  const name = stream.value.split('.')[1];

  let url = template.replace('{manifest}', manifest);
  url = url.replace('{directory}', name);
  url = url.replace('{stream}', name);
  url = url.replace("{mode}", mode.value);
  return url;
}

function updateManifestURL() {
  const stream = getSelectedStream();
  const params = buildCGI();
  const mpdUrl = calculateManifestURL(params);
  let dest = $('a.selected-stream');
  if (mpdUrl === null) {
    dest.text('');
    dest.attr('href','');
    $('.play-button').addClass('disabled');
    $('#dashurl').text('');
    $('.view-manifest').addClass('disabled');
    return;
  }
  let url = mpdUrl.replace(/^\/dash/, '/play');
  url = url.replace(/^\/mps/, '/play/mps');
  url = url.replace(/\.mpd$/, '/index.html');
  const params_str = Object.values(params).join('&');
  if (params_str) {
    url += `?${params_str}`;
  }
  $('a.selected-stream .title').text(`Play ${stream.title}`);
  dest.attr('href', document.location.origin + url);
  $('.play-button').removeClass('disabled');
  $('#with-modules .view-manifest').removeClass('disabled');

  dest = $('#dashurl');
  if (params_str) {
    dest.text(`${mpdUrl}?${params_str}`);
    dest.attr('href', `${document.location.origin}${mpdUrl}?${params_str}`);
  } else {
    dest.text(mpdUrl);
    dest.attr('href', document.location.origin + mpdUrl);
  }
  dest.removeClass('disabled');
  const viewUrl = dest.attr('href').replace(/\/(dash|mps)\//, '/view/$1/')
  $('.view-manifest').attr('href', viewUrl);
  $('#radio-mode-odvod').attr('disabled', /^mps\./.test(stream.value));

  if(window.history && typeof(history.pushState)==="function") {
    const page_params = Object.values(params);
    const modelManifest = $('#model-manifest').val()
    page_params.push(`manifest=${modelManifest}`);
    url = `${pageState.baseurl}#${page_params.join('&')}`;
    history.replaceState(
      pageState, $('#buttons tbody .manifest.selected').text(), url);
  }
}

function showOrHideAdvancedOptions(enable) {
  if (enable) {
    $('.row.advanced').removeClass('hidden');
    $('.accordion-item.advanced').removeClass('hidden');
  } else {
    $('.row.advanced').addClass('hidden');
    $('.accordion-item.advanced').addClass('hidden');
  }
}

function updateDom() {
  $('#group-0 .accordion-header').html(`
    <span class="accordion-button">
      ${$('#group-0 .accordion-header .accordion-button').text()}
    </span>`);
  const allOptions = $("#show-all-options").detach();
  $('#group-0 .accordion-header').append(allOptions);
  $('.row-field-drm_clearkey').removeClass('hidden advanced');
  $('.row-field-drm_marlin').removeClass('hidden advanced');
  $('.row-field-drm_playready').removeClass('hidden advanced');
  $('#model-group-1').append($('.row-field-drm_clearkey').remove());
  $('#model-group-1').append($('.row-field-drm_marlin').remove());
  $('#model-group-1').append($('.row-field-drm_playready').remove());
  $('#with-modules').css('display', 'block');
  $('#buttons').remove();
}

function init() {
  const defaultFields = ['mode', 'stream', 'manifest', 'player'];
  const form = document.getElementById('id_main_form');

  updateDom();
  $('#advanced-options').on('change', (ev) => {
    showOrHideAdvancedOptions(ev.target.checked);
  });
  $('#id_main_form').on('change', updateManifestURL);

  defaultFields.forEach(name => {
    const value = localStorage.getItem(`dashlive.${name}`);
    if (value !== null) {
      form[name].value = value;
    }
    $(`input[name="${name}"], select[name="${name}"]`).on('change', (ev) => {
      const { value } = ev.target;
      if (value) {
        localStorage.setItem(`dashlive.${name}`, value);
      }
    });
  });
  if (/#/.test(document.location.href)) {
    let params = document.location.href.split('#')[1];
    params = params.split('&');
    for(let i=0; i < params.length; ++i) {
      const p = params[i].split('=');
      $(`#model-${p[0]}`).val(p[1]);
    }
  }
  updateManifestURL();
  showOrHideAdvancedOptions(
    document.getElementById('advanced-options').checked);
}

init();
