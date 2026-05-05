import { NavLink } from "react-router-dom";
import styles from "./Nav.module.css";

export default function Nav() {
  return (
    <nav className={styles.nav}>
      <span className={styles.brand}>NeuroScan</span>
      <NavLink to="/studies" className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ""}`}>Studies</NavLink>
      <NavLink to="/upload" className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ""}`}>Upload</NavLink>
      <NavLink to="/audit" className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ""}`}>Audit</NavLink>
    </nav>
  );
}
