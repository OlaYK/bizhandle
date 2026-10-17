import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  type InputHTMLAttributes,
} from "react";
import { cn } from "../../lib/cn";
import { formatCurrency } from "../../lib/format";

export interface CurrencyInputProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange"> {
  label?: string;
  error?: string;
  labelClassName?: string;
  currency?: string;
  value?: number | string | null;
  onChange?: (value: number | undefined) => void;
}

export function getCurrencyPrefix(currency = "USD"): string {
  try {
    const zeroFormatted = formatCurrency(0, currency);
    return zeroFormatted.replace(/0[\.,]00$/, "");
  } catch {
    return "$";
  }
}

function cleanNumericInput(value: string): {
  clean: string;
  integerPart: string;
  decimalPart?: string;
  hasDecimal: boolean;
} {
  let result = "";
  let hasDecimal = false;

  for (let i = 0; i < value.length; i++) {
    const ch = value[i];
    if (ch >= "0" && ch <= "9") {
      result += ch;
    } else if (ch === "." && !hasDecimal) {
      result += ".";
      hasDecimal = true;
    }
  }

  if (!result) {
    return { clean: "", integerPart: "", hasDecimal: false };
  }

  const parts = result.split(".");
  let integerPart = parts[0] || "";
  let decimalPart: string | undefined = undefined;

  // Clean leading zeroes from integer part unless it is just "0"
  if (integerPart.length > 1 && integerPart.startsWith("0")) {
    integerPart = integerPart.replace(/^0+/, "") || "0";
  }

  if (parts.length > 1) {
    hasDecimal = true;
    decimalPart = parts[1].slice(0, 2);
  }

  return {
    clean: hasDecimal ? `${integerPart}.${decimalPart ?? ""}` : integerPart,
    integerPart,
    decimalPart,
    hasDecimal,
  };
}

export function formatRawCurrencyValue(
  raw: string,
  currency = "USD",
): { formatted: string; numericValue?: number } {
  const { integerPart, decimalPart, hasDecimal, clean } =
    cleanNumericInput(raw);

  if (!clean && clean !== "0") {
    return { formatted: "", numericValue: undefined };
  }

  const prefix = getCurrencyPrefix(currency);

  let formattedInteger = "";
  if (integerPart) {
    formattedInteger = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  } else if (hasDecimal) {
    formattedInteger = "0";
  }

  let formatted = prefix + formattedInteger;
  if (hasDecimal) {
    formatted += "." + (decimalPart ?? "");
  }

  const num = Number(clean);
  const numericValue =
    Number.isNaN(num) || (clean === "." || clean === "0.") ? undefined : num;

  return { formatted, numericValue };
}

function calculateNewCursorPos(
  rawStr: string,
  rawCursor: number,
  newFormattedStr: string,
  prefix: string,
): number {
  let digitsBeforeCursor = 0;
  for (let i = 0; i < rawCursor; i++) {
    const char = rawStr[i];
    if ((char >= "0" && char <= "9") || char === ".") {
      digitsBeforeCursor++;
    }
  }

  if (digitsBeforeCursor === 0) {
    return prefix.length;
  }

  let digitsSeen = 0;
  let newCursorPos = newFormattedStr.length;
  for (let i = 0; i < newFormattedStr.length; i++) {
    const char = newFormattedStr[i];
    if ((char >= "0" && char <= "9") || char === ".") {
      digitsSeen++;
    }
    if (digitsSeen === digitsBeforeCursor) {
      newCursorPos = i + 1;
      break;
    }
  }
  return newCursorPos;
}

export const CurrencyInput = forwardRef<HTMLInputElement, CurrencyInputProps>(
  function CurrencyInput(
    {
      label,
      error,
      className,
      labelClassName,
      currency = "USD",
      value,
      onChange,
      placeholder,
      onFocus,
      onBlur,
      onKeyDown,
      ...props
    },
    ref,
  ) {
    const inputRef = useRef<HTMLInputElement>(null);
    useImperativeHandle(ref, () => inputRef.current as HTMLInputElement);

    const isFocusedRef = useRef(false);
    const lastEmittedValueRef = useRef<number | undefined>(undefined);

    const initialDisplayValue = () => {
      if (value === undefined || value === null || value === "") return "";
      const num =
        typeof value === "number"
          ? value
          : Number(String(value).replace(/[^0-9.-]+/g, ""));
      return Number.isNaN(num) ? "" : formatCurrency(num, currency);
    };

    const [displayValue, setDisplayValue] = useState<string>(initialDisplayValue);

    // Sync external changes (e.g. form reset or prefilling)
    useEffect(() => {
      if (isFocusedRef.current && value === lastEmittedValueRef.current) {
        return;
      }
      if (value === undefined || value === null || value === "") {
        setDisplayValue("");
        lastEmittedValueRef.current = undefined;
        return;
      }
      const num =
        typeof value === "number"
          ? value
          : Number(String(value).replace(/[^0-9.-]+/g, ""));
      if (Number.isNaN(num)) {
        setDisplayValue("");
        lastEmittedValueRef.current = undefined;
      } else {
        setDisplayValue(formatCurrency(num, currency));
        lastEmittedValueRef.current = num;
      }
    }, [value, currency]);

    const applyChange = (rawInput: string, rawCursor: number) => {
      const prefix = getCurrencyPrefix(currency);
      const { formatted, numericValue } = formatRawCurrencyValue(
        rawInput,
        currency,
      );

      const newCursor = calculateNewCursorPos(
        rawInput,
        rawCursor,
        formatted,
        prefix,
      );

      setDisplayValue(formatted);
      lastEmittedValueRef.current = numericValue;
      onChange?.(numericValue);

      // Restore cursor position on next tick after render
      requestAnimationFrame(() => {
        if (inputRef.current) {
          inputRef.current.value = formatted;
          inputRef.current.setSelectionRange(newCursor, newCursor);
        }
      });
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const raw = e.target.value;
      const rawCursor = e.target.selectionStart ?? raw.length;
      applyChange(raw, rawCursor);
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
      const input = inputRef.current;
      const prefix = getCurrencyPrefix(currency);

      if (e.key === "Backspace" && input) {
        const { selectionStart, selectionEnd } = input;
        if (
          selectionStart !== null &&
          selectionStart === selectionEnd &&
          selectionStart > 0
        ) {
          const charBefore = input.value[selectionStart - 1];
          // If backspacing a comma or whitespace separator, delete the digit before it
          if (charBefore === "," || charBefore === " ") {
            const delIdx = selectionStart - 2;
            if (delIdx >= 0) {
              e.preventDefault();
              const nextRaw =
                input.value.slice(0, delIdx) + input.value.slice(selectionStart);
              applyChange(nextRaw, delIdx);
              return;
            }
          } else if (
            selectionStart <= prefix.length &&
            input.value.length > prefix.length
          ) {
            // Prevent deleting part of the prefix when digits exist
            e.preventDefault();
            return;
          }
        }
      }

      onKeyDown?.(e);
    };

    const handleFocus = (e: React.FocusEvent<HTMLInputElement>) => {
      isFocusedRef.current = true;
      onFocus?.(e);
    };

    const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
      isFocusedRef.current = false;
      if (displayValue) {
        const { numericValue } = formatRawCurrencyValue(displayValue, currency);
        if (numericValue !== undefined) {
          const fullyFormatted = formatCurrency(numericValue, currency);
          setDisplayValue(fullyFormatted);
        }
      }
      onBlur?.(e);
    };

    const defaultPlaceholder =
      placeholder ?? formatCurrency(0, currency);

    return (
      <label className="block space-y-1.5">
        {label ? (
          <span
            className={cn(
              "text-sm font-semibold text-surface-700 dark:text-surface-100",
              labelClassName,
            )}
          >
            {label}
          </span>
        ) : null}
        <div className="relative">
          <input
            ref={inputRef}
            type="text"
            inputMode="decimal"
            placeholder={defaultPlaceholder}
            value={displayValue}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            onFocus={handleFocus}
            onBlur={handleBlur}
            className={cn(
              "h-11 w-full rounded-lg border border-surface-200 bg-white px-3 text-sm text-surface-800 shadow-sm outline-none transition placeholder:text-surface-400 focus:border-surface-400 focus:ring-2 focus:ring-surface-200 dark:border-surface-600 dark:bg-surface-800 dark:text-surface-100 dark:placeholder:text-surface-300 dark:focus:border-surface-300 dark:focus:ring-surface-600",
              error
                ? "border-red-400 focus:border-red-400 focus:ring-red-100"
                : "",
              className,
            )}
            {...props}
          />
        </div>
        {error ? <span className="text-xs text-red-600">{error}</span> : null}
      </label>
    );
  },
);
