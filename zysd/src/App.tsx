import { useMemo, useState } from 'react';

const HOURS = Array.from({ length: 24 }, (_, index) => index + 1);

const MARKET_CURVE_2026 = [
  341.377140969022, 340.47668641193036, 343.8441940924219, 340.51015031362004,
  339.7030570276497, 338.1970044482847, 327.7814617895545, 322.39622420634925,
  317.7180244175627, 311.44867191500254, 311.15194252432156, 305.9778002752176,
  307.2920234895033, 308.546908250128, 311.02408733358936, 322.58485000640036,
  338.9910652521761, 344.095083141321, 346.0136358806963, 343.6193071556579,
  342.029266641065, 340.78107771531853, 342.0506378968254, 338.2072960189452,
];

const PROVINCE_LOAD = [
  349170.991044776, 339840.463681592, 340498.999502488, 333618.408457711,
  330547.001492537, 331382.034825871, 320328.130845771, 321496.023880597,
  324319.528358209, 316296.960199005, 314252.767164179, 294630.305472637,
  291385.494029851, 296010.185572139, 301095.057711443, 324326.571144279,
  356024.695522388, 374948.485572139, 388228.758208955, 390455.511442786,
  387979.269154229, 379853.138308458, 372049.232338308, 353026.365671642,
];

const DELTA_2027 = [
  15, 15, 20, 20, 20, 20, 15, 15, -10, -30, -80, -100,
  -100, -80, -30, -10, 15, 20, 30, 30, 30, 25, 20, 15,
];

const DEFAULT_NO_PV_2026 = [
  353.66295, 390.1852, 373.8537, 376.16115, 374.91665, 365.9704,
  338.6796, 281.16485, 237.2574, 200.42405, 158.20555, 146.7185,
  138.7852, 165.9648, 195.06115, 250.00555, 292.61665, 350.56485,
  381.3167, 391.3037, 394.38145, 392.58885, 388.60925, 385.0037,
];

const DEFAULT_CUSTOMER_2027 = [
  9945.1357, 12348.4724, 12188.5427, 12216.3668, 12316.005, 13374.8844,
  14851.5075, 15569.4523, 15925.3467, 16259.0251, 16344.9246, 16528.2211,
  16468.0352, 16086.3618, 16357.3317, 16696.7487, 16828.0754, 17174.5025,
  17198.1658, 17166.4422, 16981.9698, 16593.5377, 15981.1558, 19826.7286,
];

const MARKET_CURVE_2027 = MARKET_CURVE_2026.map((value, index) => value + DELTA_2027[index]);

function toInput(value: number) {
  return value.toFixed(4).replace(/\.?0+$/, '');
}

function toNumbers(values: string[]) {
  return values.map((value) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  });
}

function weightedPrice(priceCurve: number[], loadCurve: number[]) {
  const totalLoad = loadCurve.reduce((total, value) => total + value, 0);
  if (totalLoad === 0) return null;

  return priceCurve.reduce(
    (total, price, index) => total + price * (loadCurve[index] / totalLoad),
    0,
  );
}

function formatNumber(value: number | null) {
  return value === null || !Number.isFinite(value)
    ? '--'
    : value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

type CurvePanelProps = {
  id: string;
  label: string;
  values: string[];
  onChange: (index: number, value: string) => void;
};

function CurvePanel({ id, label, values, onChange }: CurvePanelProps) {
  return (
    <section className="curve-panel" aria-labelledby={`${id}-title`}>
      <div className="panel-heading">
        <div>
          <p className="panel-kicker">负荷输入</p>
          <h2 id={`${id}-title`}>{label}</h2>
        </div>
        <span className="unit">单位：MWh</span>
      </div>
      <div className="curve-grid" role="group" aria-label={label}>
        {HOURS.map((hour, index) => (
          <label className="hour-input" key={hour}>
            <span>{`${hour}`.padStart(2, '0')}:00</span>
            <input
              aria-label={`${label} ${`${hour}`.padStart(2, '0')}:00`}
              inputMode="decimal"
              type="number"
              value={values[index]}
              onChange={(event) => onChange(index, event.target.value)}
            />
          </label>
        ))}
      </div>
    </section>
  );
}

export default function App() {
  const [noPv2026, setNoPv2026] = useState(() => DEFAULT_NO_PV_2026.map(toInput));
  const [customer2027, setCustomer2027] = useState(() => DEFAULT_CUSTOMER_2027.map(toInput));

  const results = useMemo(() => {
    const province2026 = weightedPrice(MARKET_CURVE_2026, PROVINCE_LOAD);
    const customer2026 = weightedPrice(MARKET_CURVE_2026, toNumbers(noPv2026));
    const province2027 = weightedPrice(MARKET_CURVE_2027, PROVINCE_LOAD);
    const customerWeighted2027 = weightedPrice(MARKET_CURVE_2027, toNumbers(customer2027));

    return {
      curve2026: province2026 === null || customer2026 === null ? null : province2026 - customer2026,
      curve2027: province2027 === null || customerWeighted2027 === null ? null : province2027 - customerWeighted2027,
    };
  }, [noPv2026, customer2027]);

  const updateCurve = (
    setter: React.Dispatch<React.SetStateAction<string[]>>,
    index: number,
    value: string,
  ) => setter((current) => current.map((item, itemIndex) => (itemIndex === index ? value : item)));

  const reset = () => {
    setNoPv2026(DEFAULT_NO_PV_2026.map(toInput));
    setCustomer2027(DEFAULT_CUSTOMER_2027.map(toInput));
  };

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="section-label">价格参数</p>
          <h1>江苏电力曲线计算器</h1>
          <p className="intro">基于全省负荷与客户负荷加权均价，实时比较曲线优势。</p>
        </div>
        <button className="reset-button" type="button" onClick={reset}>恢复默认值</button>
      </header>

      <section className="result-strip" aria-label="计算结果">
        <article className="result-card">
          <span>2026 曲线优势/均价</span>
          <strong>{formatNumber(results.curve2026)}</strong>
        </article>
        <article className="result-card">
          <span>2027 曲线优势/均价</span>
          <strong>{formatNumber(results.curve2027)}</strong>
        </article>
      </section>

      <div className="input-stack">
        <CurvePanel
          id="no-pv-2026"
          label="2026 无光伏客户负荷曲线"
          values={noPv2026}
          onChange={(index, value) => updateCurve(setNoPv2026, index, value)}
        />
        <CurvePanel
          id="customer-2027"
          label="2027 客户负荷曲线"
          values={customer2027}
          onChange={(index, value) => updateCurve(setCustomer2027, index, value)}
        />
      </div>
    </main>
  );
}
