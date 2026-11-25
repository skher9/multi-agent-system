/** Two slow pastel blobs behind every page. Decoration only: hidden from screen readers
 * and still for visitors who ask for reduced motion. */

const BLOBS = [
  "-top-20 -right-28 size-96 bg-mint",
  "top-[70vh] -left-32 size-80 bg-rose [animation-delay:-6s]",
];

export function Backdrop() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      {BLOBS.map((place) => (
        <span
          key={place}
          className={`absolute animate-drift rounded-[58%_42%_55%_45%/50%_55%_45%_50%] opacity-55 ${place}`}
        />
      ))}
    </div>
  );
}
