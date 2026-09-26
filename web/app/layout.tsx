import "./styles.css";
import "maplibre-gl/dist/maplibre-gl.css";

export const metadata = { title: "DharaNokxa", description: "Automated water distribution network design" };
export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
