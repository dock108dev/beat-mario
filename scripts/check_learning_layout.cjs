// Real-browser regression: document overflow cannot detect a one-column card.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const [url, evidence] = process.argv.slice(2);
const save = (name, value) => fs.writeFileSync(path.join(evidence, name), JSON.stringify(value, null, 2));
(async () => {
  const browser = await chromium.launch({headless: true});
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  page.on('console', message => {if (message.type() === 'error') errors.push(message.text());});
  let width;
  try {
    for (width of [820, 1440, 390]) {
      await page.setViewportSize({width, height: width === 390 ? 844 : 900});
      assert.equal((await page.goto(`${url}/mario`)).status(), 200);
      const card = page.locator('#learning');
      await card.waitFor();
      // Reach Learning with actual Tab dispatch, then open its details with Enter.
      let reached = false;
      for (let n = 0; n < 120; n++) {
        await page.keyboard.press('Tab');
        reached = await page.evaluate(() => document.activeElement.matches('#learning [data-testid="learning-attempts"] > summary'));
        if (reached) break;
      }
      assert.ok(reached, 'Learning details must be keyboard reachable');
      await page.keyboard.press('Enter');
      await page.evaluate(() => {
        window.layoutReplacements = 0;
        new MutationObserver(() => window.layoutReplacements++).observe(
          document.querySelector('#active-workspace'), {childList: true});
      });
      await page.waitForFunction(() => window.layoutReplacements >= 3);
      const focus = await page.evaluate(() => ({
        held: document.activeElement.matches('#learning [data-testid="learning-attempts"] > summary'),
        open: document.querySelector('#learning [data-testid="learning-attempts"]').open,
        replacements: window.layoutReplacements,
        outline: getComputedStyle(document.activeElement).outlineStyle,
      }));
      save(`focus-${width}.json`, focus);
      assert.ok(focus.held && focus.open && focus.outline !== 'none', 'Visible keyboard focus and open details must survive real polling');
      const geometry = await card.evaluate(card => {
        const box = card.getBoundingClientRect();
        const grid = document.querySelector('.companion-main').getBoundingClientRect();
        const clipped = [];
        const walker = document.createTreeWalker(card, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {
          const node = walker.currentNode;
          if (!node.textContent.trim() || node.parentElement.closest('select, option')) continue;
          if (!node.parentElement.checkVisibility()) continue;
          const range = document.createRange(); range.selectNodeContents(node);
          for (const rect of range.getClientRects()) {
            if (rect.width && (rect.left < box.left + 1 || rect.right > box.right - 1)) {
              clipped.push(node.textContent.trim()); break;
            }
          }
        }
        const controls = [...card.querySelectorAll('select')].map(el => {
          const style = getComputedStyle(el);
          const canvas = document.createElement('canvas').getContext('2d');
          canvas.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
          return {
            name: el.name, width: el.getBoundingClientRect().width,
            // Reserve the native dropdown arrow as well as text and padding.
            requiredWidth: canvas.measureText(el.selectedOptions[0].text).width +
              parseFloat(style.paddingLeft) + parseFloat(style.paddingRight) + 20,
            inside: el.getBoundingClientRect().right <= box.right - 1,
          };
        });
        return {width: box.width, gridWidth: grid.width, left: box.left, gridLeft: grid.left,
          pageWidth: document.documentElement.scrollWidth, viewport: innerWidth,
          contentWidth: card.clientWidth - parseFloat(getComputedStyle(card).paddingLeft) - parseFloat(getComputedStyle(card).paddingRight),
          clipped, controls, columns: getComputedStyle(document.querySelector('#learning .objective-controls')).gridTemplateColumns};
      });
      save(`layout-${width}.json`, geometry);
      await card.screenshot({path: path.join(evidence, `learning-${width}.png`)});
      await page.screenshot({path: path.join(evidence, `mario-${width}.png`), fullPage: true});
      assert.ok(Math.abs(geometry.width - geometry.gridWidth) <= 1, 'Learning must span the full grid');
      assert.ok(Math.abs(geometry.left - geometry.gridLeft) <= 1);
      assert.ok(geometry.contentWidth >= (width === 390 ? 340 : width === 820 ? 740 : 1000), 'Learning needs usable content width');
      assert.deepEqual(geometry.clipped, [], 'Rendered text must remain inside the card');
      assert.ok(geometry.controls.every(control => control.inside && control.width >= control.requiredWidth), 'Preference controls must fit their displayed label');
      assert.ok(geometry.pageWidth <= width);
      if (width === 390) assert.equal(geometry.columns.split(' ').length, 1, 'Mobile preferences must stack');
      await page.keyboard.press('Enter');
      assert.equal(await page.locator('#learning [data-testid="learning-attempts"]').evaluate(el => el.open), false);
      // Editing keeps the same select, selected value, and keyboard focus.
      let editorReached = false;
      for (let n = 0; n < 30; n++) {
        await page.keyboard.press('Tab');
        editorReached = await page.evaluate(() => document.activeElement.matches('#learning select'));
        if (editorReached) break;
      }
      assert.ok(editorReached, 'Learning preferences must be keyboard reachable');
      await page.keyboard.press('ArrowDown');
      const before = await page.evaluate(() => {
        window.layoutEditor = document.activeElement;
        return {name: layoutEditor.name, value: layoutEditor.value};
      });
      await page.waitForTimeout(2400);
      assert.ok(await page.evaluate(before => document.activeElement === window.layoutEditor && layoutEditor.name === before.name && layoutEditor.value === before.value, before));
      save(`editing-${width}.json`, {...before, held: true});
      assert.deepEqual(errors, []);
    }
    save('result.json', {status: 'PASS', widths: [820, 1440, 390], errors});
  } catch (error) {
    save('result.json', {status: 'FAILED', firstFailedWidth: width, error: String(error), errors});
    await page.screenshot({path: path.join(evidence, 'failure.png'), fullPage: true});
    process.exitCode = 1;
  } finally { await browser.close(); }
})();
