import $ from '/libs/jquery.js';
import { decode } from './prod/codec-string.js';
import { enableTooltips } from './tooltips.js';

function setCodecDescription() {
    const codecDescription = decode($('.codec-string').text());
    const details = codecDescription.split('<br>').filter((line) => line !== "");
    $('.codec-description').html(details.join('<br>'));
}

setCodecDescription();
enableTooltips();
