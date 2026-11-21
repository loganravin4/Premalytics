import { Link } from 'react-router-dom';
import { Page } from '../components/Layout';

export function NotFound() {
  return (
    <Page>
      <div className="py-24">
        <p className="display text-[clamp(5rem,18vw,10rem)] text-spot">404</p>
        <h1 className="condensed mt-6 text-3xl font-extrabold">Not in this volume</h1>
        <p className="mt-3 max-w-[50ch] text-ink-2">
          That page, match, or nation is not in the record. Links use dates and three-letter team codes, for example a
          match from 11 June between Mexico and South Africa.
        </p>
        <p className="mt-8 flex flex-wrap gap-6 font-semibold">
          <Link to="/" className="text-spot">
            Back to the volume
          </Link>
          <Link to="/wc2026?view=all" className="text-spot">
            All 104 matches
          </Link>
        </p>
      </div>
    </Page>
  );
}
