import pandas as pd
from sklearn.metrics import precision_score, recall_score, f1_score

# Step 1: Define comparison function
def compare_data(benchmark_df, new_df, columns):
    """
    Compare columns in the benchmark and new dataframes.
    Returns a dictionary of performance metrics for each column.
    """
    performance_metrics = {}

    for column in columns:
        # We need to handle missing or null values, so fill NaNs with a placeholder like empty string
        benchmark_column = benchmark_df[column].fillna('')
        new_column = new_df[column].fillna('')

        # Convert the boolean comparison (True/False) to integers (1/0)
        y_true = benchmark_column != ''
        y_pred = new_column != ''

        # Calculate Precision, Recall, and F1 Score (now with the proper y_true and y_pred)
        precision = precision_score(y_true, y_pred, average='weighted', zero_division=0)
        recall = recall_score(y_true, y_pred, average='weighted', zero_division=0)
        f1 = f1_score(y_true, y_pred, average='weighted', zero_division=0)

        # Store the performance metrics for this column
        performance_metrics[column] = {'precision': precision, 'recall': recall, 'f1_score': f1}

    return performance_metrics


# Step 2: Main function that orchestrates the whole process
def main():
    # Load the benchmark dataset and new OCR output
    benchmark_df = pd.read_csv("invoice_output.csv")  # Benchmark dataset (known output)
    new_df = pd.read_csv("invoice_output_second.csv")  # New OCR output after rerun

    # Columns to compare
    columns_to_compare = [
        'invoice_number', 'date', 'cuin', 'vendor_name', 'vendor_address',
        'vendor_contact', 'po_number', 'sub_total',
        'total_amount', 'currency', 'total_tax_amount', 'goods_services_details'
    ]
    
    # Step 3: Compare the data and calculate performance
    performance_results = compare_data(benchmark_df, new_df, columns_to_compare)

    # Step 4: Output the performance results to a CSV file
    performance_df = pd.DataFrame(performance_results).T  # Transpose the results for better readability
    performance_df.to_csv("ocr_performance_comparison.csv", index=True)

    # Step 5: Optionally, print the performance metrics for review
    print(performance_df)


# Run the main function when the script is executed
if __name__ == "__main__":
    main()
