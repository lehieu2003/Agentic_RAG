import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import App from './App';

describe('App Smoke Test', () => {
  it('renders application workspace shell', () => {
    render(<App />);
    expect(screen.getByRole('banner')).toBeInTheDocument();
  });
});
