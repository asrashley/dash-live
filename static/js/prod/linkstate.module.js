var t,r=(function(t,r){t.exports=function(t,r,e,n,o){for(r=r.split?r.split("."):r,n=0;n<r.length;n++)t=t?t[r[n]]:o;return t===o?e:t}}(t={path:void 0,exports:{},require:function(t,r){return function(){throw new Error("Dynamic requires are not currently supported by @rollup/plugin-commonjs")}()}}),t.exports);export default function(t,e,n){var o=e.split("."),u=t.__lsc||(t.__lsc={});return u[e+n]||(u[e+n]=function(e){for(var u=e&&e.target||this,i={},c=i,s="string"==typeof n?r(e,n):u&&u.nodeName?u.type.match(/^che|rad/)?u.checked:u.value:e,a=0;a<o.length-1;a++)c=c[o[a]]||(c[o[a]]=!a&&t.state[o[a]]||{});c[o[a]]=s,t.setState(i)})}
//# sourceMappingURL=linkstate.module.js.map