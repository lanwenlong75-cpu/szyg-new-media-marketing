({selector, maxNodes = 240} = {}) => {
  // Read-only DOM sampling. Use a selector observed in the current page.
  const root = selector ? document.querySelector(selector) : null;
  if (!root) return {status: 'unavailable', reason: '正文容器不存在', selector};
  const styleOf = element => {
    const css = getComputedStyle(element);
    const box = element.getBoundingClientRect();
    return {
      fontFamily: css.fontFamily, fontSize: css.fontSize, fontWeight: css.fontWeight,
      color: css.color, backgroundColor: css.backgroundColor, lineHeight: css.lineHeight,
      letterSpacing: css.letterSpacing, textAlign: css.textAlign,
      marginTop: css.marginTop, marginBottom: css.marginBottom,
      paddingTop: css.paddingTop, paddingBottom: css.paddingBottom,
      paddingLeft: css.paddingLeft, paddingRight: css.paddingRight,
      width: box.width, height: box.height, x: box.x, y: box.y + scrollY
    };
  };
  const elements = [...root.querySelectorAll('h1,h2,h3,h4,p,blockquote,figure,figcaption,strong,hr,img')];
  const rendered = elements.filter(element => {
    const box = element.getBoundingClientRect();
    const css = getComputedStyle(element);
    return box.width > 0 && box.height > 0 && css.visibility !== 'hidden' && css.display !== 'none';
  });
  const limit = Math.max(1, Math.min(800, Number(maxNodes) || 240));
  return {
    status: 'sampled', selector, url: location.href, title: document.title,
    viewport: {width: innerWidth, height: innerHeight, devicePixelRatio},
    contentText: root.innerText, root: styleOf(root),
    totalRenderedNodes: rendered.length, truncated: rendered.length > limit,
    nodes: rendered.slice(0, limit).map((element, index) => ({
      position: index + 1, tag: element.tagName.toLowerCase(),
      text: element.tagName === 'IMG' ? (element.getAttribute('alt') || '') : (element.innerText || '').slice(0, 180),
      style: styleOf(element),
      ...(element.tagName === 'IMG' ? {image: {
        src: element.currentSrc || element.getAttribute('src'),
        loaded: element.complete && element.naturalWidth > 0,
        naturalWidth: element.naturalWidth, naturalHeight: element.naturalHeight
      }} : {})
    }))
  };
}
